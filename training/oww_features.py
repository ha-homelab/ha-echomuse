"""EchoMuse-compatible 80 ms streaming features; no microphone access."""
from pathlib import Path
import numpy as np
import onnxruntime as ort


def session(path):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


class Features:
    def __init__(self, assets):
        self.mel = session(Path(assets) / "melspectrogram.onnx")
        self.emb = session(Path(assets) / "embedding_model.onnx")

    def embeddings(self, pcm):
        """Batch equivalent of the device stream, including initial mel padding.

        PCM is float32 at int16 scale, never normalized to [-1, 1]. Only
        complete 1280-sample chunks count. Returns one embedding per chunk.
        """
        pcm = np.asarray(pcm, dtype=np.float32)
        n = len(pcm) // 1280
        if not n:
            return np.empty((0, 96), np.float32)
        raw = self.mel.run(None, {self.mel.get_inputs()[0].name: pcm[None, :n*1280]})[0]
        mel = np.concatenate([np.ones((76, 32), np.float32), raw.reshape(-1, 32)/10+2])
        # The first 1280 samples yield five mel frames; each later chunk eight.
        windows = np.stack([mel[5+8*i:81+8*i] for i in range(n)])
        out = []
        for start in range(0, n, 128):
            out.append(self.emb.run(None, {self.emb.get_inputs()[0].name:
                       windows[start:start+128, :, :, None]})[0].reshape(-1, 96))
        return np.concatenate(out)

    def stream_embeddings(self, pcm):
        """Literal reference matching device/internal/wakeword/stream.go."""
        pcm = np.asarray(pcm, np.float32)
        mel = np.ones((76, 32), np.float32)
        out = []
        for end in range(1280, len(pcm)+1, 1280):
            part = pcm[max(0, end-1760):end]
            raw = self.mel.run(None, {self.mel.get_inputs()[0].name: part[None]})[0]
            mel = np.concatenate([mel, raw.reshape(-1,32)/10+2])[-970:]
            out.append(self.emb.run(None, {self.emb.get_inputs()[0].name:
                       mel[None, -76:, :, None]})[0].reshape(96))
        return np.asarray(out)


def windows(embeddings):
    """Every classifier input, aligned to times 1.28, 1.36, ... seconds."""
    if len(embeddings) < 16:
        return np.empty((0, 16, 96), np.float32)
    return np.lib.stride_tricks.sliding_window_view(embeddings, 16, axis=0).transpose(0, 2, 1)
