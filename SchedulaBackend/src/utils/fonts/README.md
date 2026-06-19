# Bundled fonts

`DejaVuSans.ttf` is bundled here so PDF exports can render Hebrew (and other
Unicode) text reliably without depending on fonts installed on the host /
container. It is registered with reportlab in `src/utils/schedule_export.py`.

- Font: DejaVu Sans (covers Latin + Hebrew)
- License: Bitstream Vera / DejaVu license (permissive, redistributable)
- Source: https://dejavu-fonts.github.io/
