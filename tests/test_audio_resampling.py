import numpy as np

from core.client.audio.recorder import StreamingAudioConverter, prepare_audio_for_server


def test_resamples_stereo_48k_to_mono_16k():
    source_rate = 48000
    duration = 0.25
    time_axis = np.arange(int(source_rate * duration), dtype=np.float32) / source_rate
    tone = np.sin(2 * np.pi * 440 * time_axis).astype(np.float32)
    stereo = np.column_stack((tone, tone))

    result = prepare_audio_for_server(stereo, source_rate)

    assert result.dtype == np.float32
    assert result.shape == (4000,)
    assert np.max(np.abs(result)) > 0.9


def test_keeps_native_16k_audio_contiguous():
    source = np.arange(160, dtype=np.float32)

    result = prepare_audio_for_server(source, 16000)

    assert np.array_equal(result, source)
    assert result.flags.c_contiguous


def test_streaming_resampler_matches_continuous_reference():
    for source_rate in (44100, 48000):
        time_axis = np.arange(source_rate, dtype=np.float32) / source_rate
        source = np.sin(2 * np.pi * 997 * time_axis).astype(np.float32)
        converter = StreamingAudioConverter(source_rate)
        block_size = int(source_rate * 0.05)
        chunks = [
            converter.process(source[offset:offset + block_size])
            for offset in range(0, len(source), block_size)
        ]
        chunks.append(converter.process(np.empty(0, dtype=np.float32), last=True))

        streamed = np.concatenate(chunks)
        reference = prepare_audio_for_server(source, source_rate)

        assert streamed.shape == reference.shape == (16000,)
        assert np.max(np.abs(streamed - reference)) < 1e-6
