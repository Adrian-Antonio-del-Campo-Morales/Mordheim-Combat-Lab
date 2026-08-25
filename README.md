# Mordheim Combat Lab

> **Beta release — v0.9.0-beta.1.** An unofficial Windows desktop tool for
> analysing one-on-one Mordheim close combat through Monte Carlo simulation.

[English](#english) · [Español](#español)

## English

Mordheim Combat Lab combines the Mordheimer and Trollheim collections in one
schema-versioned knowledge base and one combat engine. It provides 83 warbands
and 540 warrior profiles, with Core, 1A, 1B, 1C, and Trollheim catalogue filters.

### Highlights

- Configure candidates and opponents from source-specific warband profiles.
- Compare weapons, equipment, advances, house rules, and MOTTA rankings.
- Run cancellable Monte Carlo simulations and export reusable Excel workbooks.
- Use the interface in English or Spanish. Movement is displayed in inches in
  English and centimetres in Spanish while retaining the same game value.
- Keep source variants explicit where rules, costs, equipment, or rosters differ.

### Install on Windows

1. Download `Mordheim-Combat-Lab-Setup-0.9.0.exe` from the latest release.
2. Run the installer. No administrator privileges are required.
3. Open **Mordheim Combat Lab** from the Start menu or desktop shortcut.

You can also download `MordheimCombatLab.exe` for a portable build.

### Run from source

Python 3.10 or later is required.

```powershell
python -m pip install -r requirements.txt
python Mordheim_Combat_Lab.py
```

### Development checks

```powershell
python tools\validate_knowledge_base.py
python tools\validate_runtime_knowledge.py
python -m pytest -q
```

The detailed review of translated and equivalent warbands is available in
[`notes/warband-equivalence-audit.md`](notes/warband-equivalence-audit.md).

## Español

Mordheim Combat Lab unifica las colecciones de Mordheimer y Trollheim en una
única base de conocimiento versionada y un único motor de combate. Incluye 83
bandas y 540 perfiles, con filtros para Básicas, 1A, 1B, 1C y Trollheim.

### Funciones principales

- Configura candidatos y oponentes con perfiles propios de cada fuente.
- Compara armas, equipo, avances, reglas caseras y clasificaciones MOTTA.
- Ejecuta simulaciones Monte Carlo cancelables y exporta libros de Excel reutilizables.
- Usa la interfaz en inglés o español. El movimiento se muestra en pulgadas en
  inglés y en centímetros en español, conservando el mismo valor de juego.
- Mantiene las variantes de cada fuente cuando cambian reglas, costes, equipo o plantilla.

### Instalar en Windows

1. Descarga `Mordheim-Combat-Lab-Setup-0.9.0.exe` de la última versión publicada.
2. Ejecuta el instalador; no requiere permisos de administrador.
3. Abre **Mordheim Combat Lab** desde el menú Inicio o el acceso directo del escritorio.

También puedes descargar `MordheimCombatLab.exe` como versión portable.

### Ejecutar desde el código fuente

Se necesita Python 3.10 o posterior.

```powershell
python -m pip install -r requirements.txt
python Mordheim_Combat_Lab.py
```

## Legal

Mordheim, Trollheim, and related names and rules belong to their respective
rights holders. This is an unofficial analytical tool and is not affiliated
with or endorsed by any rights holder.
