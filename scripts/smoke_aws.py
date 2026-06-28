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
    storage = S3StorageAdapter(
        bucket=s.s3_bucket_name,
        region=s.aws_region,
        access_key=s.aws_access_key_id or None,
        secret_key=s.aws_secret_access_key or None,
    )
    chave_s3 = "smoke/laudo_exemplo.txt"
    uri = storage.salvar(chave_s3, laudo.encode("utf-8"))
    print(f"[S3] OK -> {uri}")
    de_volta = storage.ler(uri).decode("utf-8")
    print(f"[S3] leitura de volta OK ({len(de_volta)} caracteres).")

    comprehend_ok = False
    try:
        # ---- Comprehend ----
        print("[Comprehend] DetectSentiment + DetectEntities (1 chamada cada)...")
        nlp = ComprehendAdapter(
            region=s.aws_region,
            language="pt",
            access_key=s.aws_access_key_id or None,
            secret_key=s.aws_secret_access_key or None,
        )
        resultado = nlp.analisar(laudo)
        print(f"[Comprehend] sentimento: {resultado.sentimento.rotulo} "
              f"(score={resultado.sentimento.score})")
        print(f"[Comprehend] {len(resultado.entidades)} entidades detectadas.")
        for e in resultado.entidades[:8]:
            print(f"   - {e.texto} ({e.tipo})")
        comprehend_ok = True
    except Exception as exc:  # noqa: BLE001
        # Erro do Comprehend e ESPERADO/INFORMATIVO (ex.: SubscriptionRequiredException
        # no Free Plan sem credito). Mostramos de forma limpa, sem traceback, e seguimos
        # para a limpeza do S3. NAO ha cobranca: a AWS apenas recusa o servico.
        print(f"[Comprehend] INDISPONIVEL: {type(exc).__name__}: {exc}")
    finally:
        # LIMPEZA: remove o objeto de teste do bucket SEMPRE (mesmo se o Comprehend
        # falhar), para nao deixar residuo no S3.
        try:
            storage.client.delete_object(Bucket=storage.bucket, Key=chave_s3)
            print(f"[S3] limpeza OK -> objeto de teste '{chave_s3}' removido.")
        except Exception as exc:  # noqa: BLE001
            print(f"[S3] aviso: nao consegui remover '{chave_s3}': {exc}")

    # Resumo: S3 sempre testado aqui; Comprehend e opcional (pode estar indisponivel).
    print("\nSMOKE_AWS_OK" if comprehend_ok else "\nSMOKE_S3_OK (Comprehend indisponivel)")


if __name__ == "__main__":
    main()
