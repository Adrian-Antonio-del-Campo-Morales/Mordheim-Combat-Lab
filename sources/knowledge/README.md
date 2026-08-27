# Base de conocimiento

Este directorio es la única fuente de datos del runtime. Las bandas están
separadas en identidad, perfiles, acceso a equipo y reglas locales; los
catálogos comparten mecánicas mediante IDs estables.

El runtime usa únicamente `combat_traits` normalizados. Las reglas editoriales
que no afectan a un duelo 1 contra 1 permanecen documentadas, pero no se
infieren ni ejecutan.

## Metadatos canónicos de implementación

Las reglas con una evaluación explícita del runtime declaran un bloque
`runtime` conforme a `registry/runtime-schema.yaml`. El ID de la regla conserva
su identidad editorial; las implementaciones equivalentes comparten un binding
canónico de tipo `mechanic` o `trait`. Los bindings `profile` señalan datos de
construcción normalizados en `profiles.yaml`; los bindings `compiler` son
transitorios.

La implementación es binaria (`YES` o `NO`). Una regla solo puede marcarse
`YES` cuando todos sus efectos con `scope: YES` tienen un binding ejecutable.
La ausencia del bloque `runtime` significa que la regla aún no ha sido
clasificada, no que esté fuera de alcance ni que esté implementada.
