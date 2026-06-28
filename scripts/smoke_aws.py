"""
SMOKE TEST da camada de NUVEM (OPT-IN, NAO roda no pytest).

Faz UMA passada minima pela AWS para confirmar que a sua conta permite os servicos:
  1. Sobe o texto do laudo sintetico no S3 (S3StorageAdapter).
  2. Chama o Comprehend (DetectSentiment + DetectEntities) uma vez (ComprehendAdapter).

Tudo via os MESMOS adapters do app (nada de boto3 solto aqui).

----------------------------------------------------------------------------
COMO RODAR (precisa de credenciais AWS no seu .env e um bucket S3 existente):

  # 1) configure no .env (NUNCA commitar):
  #    AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...  AWS_REGION=us-east-1
  #    S3_BUCKET_NAME=seu-bucket
  # 2) habilite o smoke e rode:
  PowerShell:  $env:RUN_AWS_SMOKE=1; python scripts/smoke_aws.py
  Bash:        RUN_AWS_SMOKE=1 python scripts/smoke_aws.py

ATENCAO LGPD/custo:
- Comprehend consome credito e ENVIA o texto a um servico de terceiros (AWS).
  Use SOMENTE o laudo SINTETICO. Sao pouquissimas chamadas (1 de cada).
- Se a conta nao permitir o servico, o erro da AWS aparece aqui -> e o que queremos
  descobrir antes da demo.
----------------------------------------------------------------------------
"""

from __future__ import annotations

import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend.app.core.config import get_settings  # noqa: E402
from backend.app.ports.nlp import ComprehendAdapter  # noqa: E402
from backend.app.ports.storage import S3StorageAdapter  # noqa: E402


def main() -> None:
    # trava de seguranca: so roda se explicitamente habilitado
    if os.getenv("RUN_AWS_SMOKE") != "1":
        raise SystemExit(
            "Smoke de AWS desabilitado. Defina RUN_AWS_SMOKE=1 para rodar "
            "(e configure credenciais no .env)."
        )

    s = get_settings()
    if not s.s3_bucket_name:
        raise SystemExit("Defina S3_BUCKET_NAME no .env.")

    laudo = (RAIZ / "data/samples/laudo_exemplo.txt").read_text(encoding="utf-8")

    # ---- S3 ----
    print(f"[S3] subindo laudo sintetico no bucket '{s.s3_bucket_name}'...")
    storage = S3StorageAdapter(bucket=s.s3_bucket_name, region=s.aws_region)
    uri = storage.salvar("smoke/laudo_exemplo.txt", laudo.encode("utf-8"))
    print(f"[S3] OK -> {uri}")
    de_volta = storage.ler(uri).decode("utf-8")
    print(f"[S3] leitura de volta OK ({len(de_volta)} caracteres).")

    # ---- Comprehend ----
    print("[Comprehend] DetectSentiment + DetectEntities (1 chamada cada)...")
    nlp = ComprehendAdapter(region=s.aws_region, language="pt")
    resultado = nlp.analisar(laudo)
    print(f"[Comprehend] sentimento: {resultado.sentimento.rotulo} "
          f"(score={resultado.sentimento.score})")
    print(f"[Comprehend] {len(resultado.entidades)} entidades detectadas.")
    for e in resultado.entidades[:8]:
        print(f"   - {e.texto} ({e.tipo})")

    print("\nSMOKE_AWS_OK")


if __name__ == "__main__":
    main()
