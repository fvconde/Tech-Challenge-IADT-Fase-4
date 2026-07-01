# Frontend — IA Multimodal (Saúde da Mulher)

Frontend Angular 19 (enxuto, sem libs de UI) que demonstra o fluxo multimodal
ponta-a-ponta e o **alerta à equipe médica**. Consome a API FastAPI do backend.

> Página única: **sidebar fixa** à esquerda (entradas por modalidade) + **área central
> rolável** com os resultados/alertas retornados pela API.

## Pré-requisitos

- Node 18+ (testado com Node 22) e npm.
- **Backend rodando** em `http://127.0.0.1:8000` (ver README na raiz):
  ```bash
  uvicorn backend.app.main:app --reload
  ```
  O backend já tem **CORS** liberado para `http://localhost:4200`.

## Subir em desenvolvimento

```bash
cd frontend
npm install        # só na primeira vez
npm start          # equivale a "ng serve"
```

Abra `http://localhost:4200`.

> A URL da API fica em [src/app/core/api-config.ts](src/app/core/api-config.ts)
> (`API_BASE_URL`). Mude ali se o backend estiver em outra porta/host.

## Como usar (demo)

1. Suba o backend e gere os exemplos sintéticos (na raiz do projeto):
   ```bash
   python scripts/gerar_video_exemplo.py
   python scripts/gerar_laudo_exemplo.py
   ```
2. Na sidebar, preencha o texto e/ou selecione áudio (.wav), vídeo (.mp4/.avi/.mov),
   imagem (.jpg/.png) ou laudo (.pdf).
3. Use os botões "Analisar ..." para ver o resultado de cada modalidade.
4. Clique em **🚨 Gerar alerta (fusão)** para combinar tudo num **alerta único** à
   equipe médica (severidade, categorias, modalidades que corroboraram e ação recomendada).

## Estrutura

```
src/app/
├── core/
│   ├── api-config.ts     # URL base da API
│   ├── models.ts         # tipos TS espelhando os schemas Pydantic
│   └── api.service.ts    # service HTTP tipado (todos os endpoints)
├── shared/
│   ├── nivel-badge.component.ts   # badge de severidade (baixo/medio/alto)
│   └── alerta-card.component.ts   # card de resultado/alerta (reutilizado)
├── home/
│   ├── home.component.ts/.html/.css   # sidebar + feed de resultados
└── app.component.ts      # shell (renderiza <app-home/>)
```

## Build de produção

```bash
npm run build      # gera dist/
```

> Observação ética: o sistema **gera alertas para a equipe especializada** — não emite
> diagnóstico. Use apenas dados **sintéticos** (sem PHI).
