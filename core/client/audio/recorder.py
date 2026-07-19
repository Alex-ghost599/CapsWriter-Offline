# coding: utf-8
"""
音频录制模块

提供 AudioRecorder 类用于管理录音会话，包括开始录音、
发送音频数据到服务端、结束录音等功能。
"""

from __future__ import annotations

import base64
import uuid
from typing import TYPE_CHECKING, Optional

import numpy as np
import soxr

from config_client import ClientConfig as Config
from core.client.state import console
from core.client.audio.file_manager import AudioFileManager
from core.client.connection import WebSocketManager
from core.protocol import AudioMessage
from . import logger

if TYPE_CHECKING:
    from core.client.state import ClientState
    from core.client.app import CapsWriterClient

# 日志记录器


def _mix_to_mono(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return np.ascontiguousarray(data, dtype=np.float32)
    return np.ascontiguousarray(np.mean(data, axis=1, dtype=np.float32))


def prepare_audio_for_server(data: np.ndarray, source_sample_rate: int) -> np.ndarray:
    """Mix a complete input buffer to mono and resample it to 16 kHz."""
    mono = _mix_to_mono(data)
    if source_sample_rate == 16000:
        return mono

    return np.ascontiguousarray(soxr.resample(mono, source_sample_rate, 16000, quality='HQ'), dtype=np.float32)


class StreamingAudioConverter:
    """Stateful mono converter for the live CoreAudio stream."""

    def __init__(self, source_sample_rate: int):
        self.source_sample_rate = source_sample_rate
        self._resampler = None
        if source_sample_rate != 16000:
            self._resampler = soxr.ResampleStream(
                source_sample_rate,
                16000,
                num_channels=1,
                dtype='float32',
                quality='HQ',
            )

    def process(self, data: np.ndarray, *, last: bool = False) -> np.ndarray:
        mono = _mix_to_mono(data)
        if self._resampler is None:
            return mono
        return np.ascontiguousarray(self._resampler.resample_chunk(mono, last=last), dtype=np.float32)


class AudioRecorder:
    """
    音频录制器
    
    管理一次完整的录音会话，包括：
    - 从音频流接收数据
    - 可选地保存到本地文件
    - 将音频数据发送到识别服务端
    """
    
    def __init__(self, app: CapsWriterClient):
        """
        初始化录制器
        
        Args:
            app: 客户端 App 实例
        """
        self.app = app
        self.task_id: Optional[str] = None
        self._file_manager: Optional[AudioFileManager] = None
        self._start_time: float = 0.0
        self._duration: float = 0.0
        self._cache: list = []

    @property
    def state(self) -> ClientState:
        """快捷访问状态单例"""
        return self.app.state

    @property
    def _ws_manager(self) -> WebSocketManager:
        """快捷访问桥接到 app.ws"""
        return self.app.ws
    
    async def _send_message(self, message: AudioMessage) -> None:
        """发送消息到服务端"""
        if not self._ws_manager.is_connected:
            if message.is_final:
                self.state.pop_audio_file(message.task_id)
                console.print('    服务端未连接，无法发送\n')
                logger.warning("服务端未连接，无法发送音频数据")
            return
        
        # 使用 WebSocketManager 发送协议消息
        success = await self._ws_manager.send(message)
        if not success and message.is_final:
            self.state.pop_audio_file(message.task_id)
            # 具体错误日志由 WebSocketManager 记录
    
    async def record_and_send(self) -> None:
        """
        录音并发送数据
        
        从队列中读取音频数据，保存到文件（如果启用），
        并发送到服务端进行识别。
        """
        try:
            # 生成唯一任务 ID
            self.task_id = str(uuid.uuid1())
            logger.debug(f"创建录音任务，任务ID: {self.task_id}")
            
            self._start_time = 0.0
            self._duration = 0.0
            self._cache = []
            converter = StreamingAudioConverter(self.state.audio_sample_rate)

            async def send_audio_chunk(data: np.ndarray, *, last: bool = False) -> None:
                converted = converter.process(data, last=last)
                if not converted.size:
                    return
                message = AudioMessage(
                    task_id=self.task_id,
                    source='mic',
                    data=base64.b64encode(converted.tobytes()).decode('utf-8'),
                    is_final=False,
                    time_start=self._start_time,
                    seg_duration=Config.mic_seg_duration,
                    seg_overlap=Config.mic_seg_overlap,
                    context=Config.context,
                    language=Config.language,
                )
                await self._send_message(message)
            
            # 音频文件管理
            file_path = None
            if Config.save_audio:
                self._file_manager = AudioFileManager(sample_rate=self.state.audio_sample_rate)
            
            # 从队列读取数据
            while task := await self.state.queue_in.get():
                self.state.queue_in.task_done()
                
                if task['type'] == 'begin':
                    self._start_time = task['time']
                    logger.debug(f"录音开始，时间戳: {self._start_time}")
                    
                elif task['type'] == 'data':
                    # 在阈值之前积攒音频数据
                    if task['time'] - self._start_time < Config.threshold:
                        self._cache.append(task['data'])
                        continue
                    
                    # 创建音频文件
                    if Config.save_audio and self._file_manager and file_path is None:
                        file_path, _ = self._file_manager.create(
                            task['data'].shape[1],
                            self._start_time
                        )
                        self.state.register_audio_file(self.task_id, file_path)
                        logger.debug(f"创建音频文件: {file_path}")
                    
                    # 获取音频数据
                    if self._cache:
                        data = np.concatenate((*self._cache, task['data']))
                        self._cache.clear()
                    else:
                        data = task['data']
                    
                    # 保存音频至本地文件
                    self._duration += len(data) / self.state.audio_sample_rate
                    if Config.save_audio and self._file_manager:
                        self._file_manager.write(data)
                    
                    # 发送音频数据用于识别
                    await send_audio_chunk(data)
                    
                elif task['type'] == 'finish':
                    # 如果有缓存的数据未发送，先发送缓存
                    if self._cache:
                        data = np.concatenate(self._cache)
                        self._cache.clear()
                        
                        self._duration += len(data) / self.state.audio_sample_rate
                        if Config.save_audio and self._file_manager:
                            self._file_manager.write(data)

                        await send_audio_chunk(data)

                    await send_audio_chunk(np.empty(0, dtype=np.float32), last=True)

                    # 完成写入本地文件
                    if Config.save_audio and self._file_manager:
                        self._file_manager.finish()
                        logger.debug("完成音频文件写入")
                    
                    console.print(f'任务标识：{self.task_id}')
                    console.print(f'    录音时长：{self._duration:.2f}s')
                    logger.info(f"录音任务完成，任务ID: {self.task_id}, 时长: {self._duration:.2f}s")
                    
                    # 告诉服务端音频片段结束了
                    message = AudioMessage(
                        task_id=self.task_id,
                        source='mic',
                        data='',
                        is_final=True,
                        time_start=self._start_time,
                        seg_duration=Config.mic_seg_duration,
                        seg_overlap=Config.mic_seg_overlap,
                        context=Config.context,
                        language=Config.language,
                    )
                    await self._send_message(message)
                    break
                    
        except Exception as e:
            logger.error(f"录音任务错误: {e}", exc_info=True)
    
    def get_file_manager(self) -> Optional[AudioFileManager]:
        """获取当前的文件管理器"""
        return self._file_manager
