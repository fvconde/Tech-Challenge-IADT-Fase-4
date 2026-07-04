"""
Servico de VIDEO multimodal.

Tecnicas aplicadas ao MESMO arquivo de video/imagem, convergindo em um unico
alerta na camada de fusao:

- YOLOv8 (ultralytics) -> deteccao de objetos      -> risk_rules.py
- MediaPipe (pose)     -> sinais corporais/gestos   -> pose_rules.py
- DeepFace (emocao)    -> emocao facial aparente     -> emotion_rules.py
- moviepy + transcricao -> fala da trilha de audio   -> reusa o pipeline de texto

Tudo 100% local e custo zero. Pose/emocao/trilha sao OPT-IN (defaults mock/off):
por padrao o endpoint /api/video/analyze roda apenas o YOLO, como antes. Ativar
na demo com POSE_BACKEND=local, EMOTION_BACKEND=local, VIDEO_TRANSCREVER_AUDIO=true.

Postura etica: nenhuma tecnica emite diagnostico; todas geram INDICIOS para a
equipe especializada avaliar. O notebook notebooks/01_yolov8_demo.ipynb demonstra
o requisito de YOLOv8 isoladamente.
"""
