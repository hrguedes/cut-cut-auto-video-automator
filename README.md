# Cut Cut

Corta um vídeo em partes de duração fixa. Feito por Hugo Guedes.

## O que precisa estar instalado

- Python 3.10 ou mais novo
- FFmpeg e FFprobe, os dois da mesma versão
- PySide6, instalado pelo comando do projeto abaixo

Para gerar o aplicativo, instale também o PyInstaller dentro do ambiente virtual:

```bash
pip install pyinstaller
```

### FFmpeg

No macOS, o Homebrew instala os dois:

```bash
brew install ffmpeg
```

No Windows, use a versão estável **9.0.2**, pacote **essentials**:

https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

Da pasta `bin`, use `ffmpeg.exe` e `ffprobe.exe`. Os dois precisam ser dessa mesma pasta.

Também dá para instalar pelo winget:

```bash
winget install "FFmpeg (Essentials Build)"
```

Feche e abra o terminal. `ffmpeg -version` e `ffprobe -version` precisam funcionar.

Se o FFmpeg não estiver instalado, coloque os dois arquivos na mesma pasta do executável. No Windows, ao lado de `CutAndCut.exe`. No Mac, dentro de `CutAndCut.app/Contents/MacOS/`. O programa procura nessa pasta antes de pedir o caminho.

## Rodar em desenvolvimento

```bash
python -m venv .venv
```

No macOS:

```bash
source .venv/bin/activate
```

No Windows:

```bash
.venv\Scripts\activate
```

```bash
pip install -e ".[dev]"
python -m cut_and_cut
```

## Testes

```bash
pytest
```

## Gerar o executável

O PyInstaller não gera o programa de um sistema no outro. O comando do Mac cria o aplicativo do Mac. O comando do Windows cria o `.exe`, e só funciona no Windows.

Ative o ambiente virtual e rode o comando na pasta do projeto. A foto da página inicial entra com `--add-data`. O separador desse argumento é `:` no Mac e `;` no Windows.

### macOS

Gera `dist/CutAndCut.app`:

```bash
pyinstaller --name CutAndCut --windowed --noconfirm --collect-all PySide6 --add-data="src/cut_and_cut/assets/author.jpg:assets" src/cut_and_cut/__main__.py
```

### Windows

Gera a pasta `dist\CutAndCut\`, com `CutAndCut.exe` dentro. Rode no Prompt de Comando:

```bat
pyinstaller --name CutAndCut --windowed --noconfirm --collect-all PySide6 --add-data="src/cut_and_cut/assets/author.jpg;assets" src/cut_and_cut/__main__.py
```

Use barras normais nos caminhos. No Mac, uma barra invertida some e o PyInstaller não acha o arquivo.

O FFmpeg não entra nesse pacote. No Windows, copie `ffmpeg.exe` e `ffprobe.exe` para a mesma pasta de `CutAndCut.exe`. No Mac, copie `ffmpeg` e `ffprobe` para `CutAndCut.app/Contents/MacOS/`, ou deixe o FFmpeg do Homebrew instalado.
