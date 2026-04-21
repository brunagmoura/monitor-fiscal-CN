# Monitor Fiscal de Proposições Legislativas

Acompanhamento automatizado de proposições da Câmara dos Deputados e do
Senado Federal que podem criar exceções à **LC 200/2023** ou alterar o
cálculo da **meta de resultado primário**.

## Estrutura

- `monitor_fiscal.py` — coleta, baixa inteiro teor, classifica e salva em SQLite
- `painel.py` — dashboard Streamlit

## Execução local

```bash
pip install -r requirements.txt
python monitor_fiscal.py
streamlit run painel.py
```

## MVP

Classificação por expressões regulares em três dimensões: referência à
LC 200/2023, à meta primária e a termos de alto risco (precatórios,
FUNDEB, etc.). Score de 0 a 3.