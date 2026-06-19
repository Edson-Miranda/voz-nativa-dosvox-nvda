# Voz nativa do Dosvox para NVDA

Add-on de sintetizador para o NVDA baseado nos difones nativos do Dosvox.

## Recursos

- variantes Difones, Difones2, Difones3, difones5 e novodifo;
- controle de velocidade;
- gravações dedicadas para letras, números e símbolos;
- distinção entre símbolos reais e seus nomes escritos;
- compatibilidade testada com o NVDA 2026.1.1.

## Estrutura

- `manifest.ini`: metadados e compatibilidade do add-on;
- `synthDrivers/vozNativaDoDosvox.py`: integração com o NVDA;
- `synthDrivers/dosvox_native_core.py`: síntese, símbolos e processamento de texto;
- `synthDrivers/dosvox_data/`: bancos de difones e regras;
- `synthDrivers/Letras/`: gravações dedicadas;
- `doc/pt_BR/readme.html`: documentação exibida pelo NVDA;
- `tests/`: testes de regressão;
- `build_nvda_addon.py`: geração do pacote instalável.

## Testes

Requer Python 3. Execute:

```powershell
python .\tests\run_tests.py
```

## Compilação

```powershell
python .\build_nvda_addon.py
```

O pacote será criado em `dist/`. Essa pasta não é versionada; os pacotes publicados devem ser anexados às versões na página de Releases do GitHub.

## Instalação

Abra o arquivo `.nvda-addon` com o NVDA em execução, confirme a instalação e reinicie o NVDA.

## Licenciamento

Antes de publicar este repositório como público, confirme as condições de redistribuição dos bancos de difones, regras e gravações originados do Dosvox. Nenhuma licença nova é atribuída a esses arquivos por este repositório.

