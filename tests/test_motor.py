"""Tests de la elección de motor y la vuelta a CPU en src/engine.py (con un WhisperModel falso)."""

import sys
import types
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

engine = pytest.importorskip("src.engine", reason="hace falta el entorno completo (torch, pyannote, faster-whisper)")
from src import componentes  # noqa: E402

CUDA = componentes.Motor("small", "/modelos/whisper-small", "cuda", "float16")


class WhisperFalso:
    creados: list = []
    falla_al_crear_en_cuda = False
    falla_al_transcribir_en_cuda = False

    def __init__(self, ruta, device, compute_type, download_root):
        if device == "cuda" and WhisperFalso.falla_al_crear_en_cuda:
            raise RuntimeError("CUDA driver version is insufficient")
        self.device = device
        WhisperFalso.creados.append((ruta, device, compute_type))

    def transcribe(self, audio, **kwargs):
        assert isinstance(audio, np.ndarray)  # el audio llega leído, no como ruta
        info = types.SimpleNamespace(language="es", language_probability=0.99, duration=2.0)

        def segmentos():
            if self.device == "cuda" and WhisperFalso.falla_al_transcribir_en_cuda:
                raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
            yield types.SimpleNamespace(start=0.0, end=2.0, text=" hola ", words=[])

        return segmentos(), info


@pytest.fixture
def wav(tmp_path):
    ruta = tmp_path / "a.wav"
    sf.write(ruta, np.zeros(32000, dtype="float32"), 16000)
    return ruta


@pytest.fixture(autouse=True)
def motor_limpio(monkeypatch):
    WhisperFalso.creados = []
    WhisperFalso.falla_al_crear_en_cuda = WhisperFalso.falla_al_transcribir_en_cuda = False
    monkeypatch.setattr(engine, "WhisperModel", WhisperFalso)
    monkeypatch.setattr(engine, "_whisper_model", None)
    monkeypatch.setattr(engine, "_motor", None)
    monkeypatch.setattr(componentes, "elegir_motor", lambda: CUDA)


def test_carga_el_modelo_y_la_placa_elegidos(wav):
    segmentos, meta = engine.transcribir_whisper(wav, 2.0)
    assert WhisperFalso.creados == [("/modelos/whisper-small", "cuda", "float16")]
    assert segmentos[0]["text"] == "hola" and engine.motor_actual() == CUDA


def test_si_la_placa_no_carga_sigue_en_cpu(wav):
    WhisperFalso.falla_al_crear_en_cuda = True
    segmentos, _ = engine.transcribir_whisper(wav, 2.0)
    assert segmentos[0]["text"] == "hola"
    assert engine.motor_actual().dispositivo == "cpu" and engine.motor_actual().modelo == "small"


def test_si_la_placa_falla_en_el_medio_reintenta_en_cpu_y_avisa(wav):
    WhisperFalso.falla_al_transcribir_en_cuda = True
    avisos = []
    segmentos, _ = engine.transcribir_whisper(wav, 2.0, progress_callback=lambda **k: avisos.append(k["stage"]))
    assert segmentos[0]["text"] == "hola"
    assert [c[1] for c in WhisperFalso.creados] == ["cuda", "cpu"]
    assert any("placa de video falló" in a for a in avisos)


def test_un_error_en_cpu_no_se_tapa(wav, monkeypatch):
    monkeypatch.setattr(componentes, "elegir_motor", lambda: componentes.motor_cpu())
    monkeypatch.setattr(WhisperFalso, "transcribe", lambda self, a, **k: (_ for _ in ()).throw(RuntimeError("otro error")))
    with pytest.raises(RuntimeError, match="otro error"):
        engine.transcribir_whisper(wav, 2.0)


def test_cancelar_no_dispara_la_vuelta_a_cpu(wav):
    import threading

    cancelar = threading.Event()
    cancelar.set()
    with pytest.raises(InterruptedError):
        engine.transcribir_whisper(wav, 2.0, cancel_event=cancelar)
    assert engine.motor_actual().dispositivo == "cuda"
