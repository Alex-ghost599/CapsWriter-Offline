# coding: utf-8
"""
WebSocket 接收处理模块

处理客户端发送的音频数据，进行分段和缓冲，提交到识别队列。
"""

import json
import math
import time
from base64 import b64decode

import websockets

from ..state import console
from ..schema import Task
from config_server import ServerConfig as Config
from core.protocol import AudioMessage
from core.constants import AudioFormat
from core.tools.my_status import Status
from .. import logger


# 麦克风接收状态指示器
status_mic = Status('正在接收音频', spinner='point')


class AudioCache:
    """
    音频缓冲区

    用于缓存接收到的音频数据，直到达到分段阈值后提交处理。
    """
    def __init__(self):
        self.chunks = bytearray()    # 音频数据缓冲
        self.offset: float = 0.0    # 当前偏移时间（秒）
        self.byte_count: int = 0    # 累计接收字节数
        self.task_signature = None

    @property
    def duration(self) -> float:
        """缓冲区音频时长（秒）"""
        return AudioFormat.bytes_to_seconds(len(self.chunks))

    @property
    def total_duration(self) -> float:
        """累计接收的音频总时长（秒）"""
        return AudioFormat.bytes_to_seconds(self.byte_count)

    def reset(self) -> None:
        """重置缓冲区"""
        self.chunks.clear()
        self.offset = 0.0
        self.byte_count = 0
        self.task_signature = None

    def validate_sequence(self, msg: AudioMessage) -> None:
        signature = (msg.task_id, msg.source, msg.seg_duration, msg.seg_overlap)
        if self.task_signature is None:
            self.task_signature = signature
        elif signature != self.task_signature:
            raise ValueError('同一连接不能混合不同音频任务或分段配置')

    def append(self, data: bytes) -> None:
        next_total = self.byte_count + len(data)
        max_total = AudioFormat.seconds_to_bytes(Config.max_audio_seconds)
        if next_total > max_total:
            raise ValueError(f'单个任务音频不能超过 {Config.max_audio_seconds} 秒')

        max_buffer = AudioFormat.seconds_to_bytes(
            Config.max_segment_duration + Config.max_segment_overlap * 2
        )
        if len(self.chunks) + len(data) > max_buffer:
            raise ValueError('音频缓冲超过服务端上限')
        self.chunks.extend(data)
        self.byte_count = next_total


def validate_audio_message(msg: AudioMessage) -> None:
    """Reject malformed protocol values before allocating audio buffers."""
    if msg.source not in ('mic', 'file'):
        raise ValueError('不支持的音频来源')
    if not isinstance(msg.task_id, str) or not msg.task_id or len(msg.task_id) > 128:
        raise ValueError('任务标识无效')
    if not isinstance(msg.data, str):
        raise ValueError('音频数据必须为 Base64 字符串')
    if not isinstance(msg.is_final, bool):
        raise ValueError('is_final 必须为布尔值')
    if isinstance(msg.time_start, bool) or not isinstance(msg.time_start, (int, float)) or not math.isfinite(msg.time_start):
        raise ValueError('开始时间无效')
    if (
        isinstance(msg.seg_duration, bool)
        or not isinstance(msg.seg_duration, (int, float))
        or not math.isfinite(msg.seg_duration)
    ):
        raise ValueError('分段时长无效')
    if not 0 < msg.seg_duration <= Config.max_segment_duration:
        raise ValueError(f'分段时长必须在 0 到 {Config.max_segment_duration} 秒之间')
    if (
        isinstance(msg.seg_overlap, bool)
        or not isinstance(msg.seg_overlap, (int, float))
        or not math.isfinite(msg.seg_overlap)
    ):
        raise ValueError('分段重叠时长无效')
    if not 0 <= msg.seg_overlap <= min(Config.max_segment_overlap, msg.seg_duration):
        raise ValueError('分段重叠时长超过上限')
    if not isinstance(msg.context, str) or len(msg.context) > Config.max_context_chars:
        raise ValueError('上下文长度超过上限')
    if not isinstance(msg.language, str) or len(msg.language) > 32:
        raise ValueError('语言参数无效')


async def message_handler(websocket, msg: AudioMessage, cache: AudioCache, app) -> None:
    """
    处理客户端发送的音频消息

    根据消息中的分段参数，将音频数据分段后提交到识别队列。
    """
    queue_in = app.state.queue_in

    global status_mic
    validate_audio_message(msg)
    cache.validate_sequence(msg)
    is_start = cache.byte_count == 0
    socket_id = str(websocket.id)

    # 麦克风首次消息 → GPU 加速
    if is_start and msg.source == 'mic' and Config.gpu_boost_enabled:
        queue_in.put(Task(
            type='cmd',
            task_id='gpu_boost',
            data=b'', offset=0, overlap=0,
            socket_id=socket_id, is_final=False,
            time_start=0, time_submit=0,
            command='gpu_boost'
        ))

    # 从消息中获取分段参数
    seg_threshold = msg.seg_duration + msg.seg_overlap * 2

    try:
        # base64 解码音频数据（float32, 16kHz, mono）
        data = b64decode(msg.data, validate=True)
        if len(data) > Config.max_audio_chunk_bytes:
            raise ValueError('单个音频数据块超过服务端上限')
        if len(data) % AudioFormat.BYTES_PER_SAMPLE:
            raise ValueError('音频数据不是完整的 float32 采样')
        cache.append(data)

        if not msg.is_final:
            # 打印状态消息
            if msg.source == 'mic':
                status_mic.start()
            if msg.source == 'file' and is_start:
                console.print('正在接收音频文件...')
                logger.info(f"开始接收音频文件，任务ID: {msg.task_id}")

            # 若缓冲已达到分段阈值，将片段作为任务提交
            segment_bytes = AudioFormat.seconds_to_bytes(msg.seg_duration + msg.seg_overlap)
            stride_bytes = AudioFormat.seconds_to_bytes(msg.seg_duration)

            while cache.duration >= seg_threshold:
                segment_data = bytes(cache.chunks[:segment_bytes])
                del cache.chunks[:stride_bytes]

                task = Task(
                    type=msg.source,
                    data=segment_data,
                    offset=cache.offset,
                    task_id=msg.task_id,
                    socket_id=socket_id,
                    overlap=msg.seg_overlap,
                    is_final=False,
                    time_start=msg.time_start,
                    time_submit=time.time(),
                    context=msg.context,
                    language=msg.language,
                )
                cache.offset += msg.seg_duration
                queue_in.put(task)
                logger.debug(
                    f"提交音频片段，任务ID: {msg.task_id}, "
                    f"偏移: {cache.offset}s, 缓冲区: {len(cache.chunks)} bytes"
                )

        else:  # is_final
            # 打印状态消息
            if msg.source == 'mic':
                status_mic.stop()
            elif msg.source == 'file':
                print(f'音频文件接收完毕，时长 {cache.total_duration:.2f}s')
                logger.info(f"音频文件接收完毕，任务ID: {msg.task_id}, 时长: {cache.total_duration:.2f}s")

            # 提交最终片段
            task = Task(
                type=msg.source,
                data=bytes(cache.chunks),
                offset=cache.offset,
                task_id=msg.task_id,
                socket_id=socket_id,
                overlap=msg.seg_overlap,
                is_final=True,
                time_start=msg.time_start,
                time_submit=time.time(),
                context=msg.context,
                language=msg.language,
            )
            queue_in.put(task)
            logger.debug(f"提交最终片段，任务ID: {msg.task_id}, 数据大小: {len(cache.chunks)} bytes")

            # 重置缓冲区
            cache.reset()

    except Exception as e:
        logger.error(f"音频数据处理错误，任务ID: {msg.task_id}: {e}", exc_info=True)
        raise


async def ws_recv(websocket, app) -> None:
    """
    WebSocket 接收主函数

    处理单个客户端连接，接收音频数据并分发处理。
    """
    global status_mic

    # 登记 socket 到连接池
    state = app.state
    sockets = state.sockets
    sockets_id = state.sockets_id
    socket_id = str(websocket.id)
    if len(sockets) >= Config.max_connections:
        logger.warning(f'拒绝超过连接上限的客户端: {websocket.remote_address}')
        await websocket.close(code=1013, reason='server connection limit reached')
        return
    sockets[socket_id] = websocket
    sockets_id.append(socket_id)
    remote = websocket.remote_address
    console.print(f'[bold green]客户端已连接: {remote[0]}:{remote[1]}[/bold green]\n')
    logger.info(f"新客户端连接: {websocket}, ID: {socket_id}")

    # 创建音频缓冲区
    cache = AudioCache()

    # 接收并处理消息
    try:
        async for raw_message in websocket:
            # 使用协议类解析消息
            try:
                data = json.loads(raw_message)
                msg = AudioMessage.from_dict(data)
                # 处理音频数据
                await message_handler(websocket, msg, cache, app)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
                logger.error(f"消息解析失败: {str(e)}")
                await websocket.close(code=1008, reason='invalid audio message')
                break
            except Exception as e:
                logger.error(f"消息处理失败: {str(e)}", exc_info=True)
                await websocket.close(code=1011, reason='audio message processing failed')
                break

        logger.info(f"客户端正常关闭连接: {socket_id}")

    except websockets.ConnectionClosed:
        console.print("ConnectionClosed...")
        logger.warning(f"客户端连接已关闭: {socket_id}")
    except websockets.InvalidState:
        console.print("InvalidState...")
        logger.error(f"WebSocket 状态异常: {socket_id}")
    except Exception as e:
        console.print("Exception:", e)
        logger.error(f"WebSocket 接收异常，客户端ID {socket_id}: {e}", exc_info=True)
    finally:
        # 清理资源
        status_mic.stop()
        status_mic.on = False
        sockets.pop(socket_id, None)
        if socket_id in sockets_id:
            sockets_id.remove(socket_id)

        console.print(f'[bold red]客户端已断开: {remote[0]}:{remote[1]}[/bold red]\n')

        # 注意：session 清理由 TaskHandler 在子进程中定期执行
        # （通过检查 sockets_id 判断客户端是否已断开）
        logger.debug(f"客户端资源已清理: {socket_id}")
