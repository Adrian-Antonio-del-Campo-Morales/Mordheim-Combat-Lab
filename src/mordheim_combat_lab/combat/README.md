# Combat

Fases, motor modular y vectorizado. Consume luchadores compilados y no carga YAML. Véase [Arquitectura](../../../docs/architecture.md).

## Diferencias pendientes entre motores

La evidencia semántica corresponde al motor modular, no certifica el vectorizado usado por la UI.
En `Poisonous` de la araña gigante, el modular consulta el efecto del atacante y la inmunidad del
defensor. El vectorizado todavía consulta el trait del defensor para modificar la tabla de heridas.
Queda pendiente trasladar esta corrección y verificar la paridad cuando se aborde ese motor.
La especificación de referencia es [editorial-spider-poisonous.yaml](../../../specs/semantic/grants/editorial-spider-poisonous.yaml).

El modular también incluye la contribución de Iniciativa del arma secundaria al resolver
el orden de actuación. El vectorizado todavía suma solo el arma principal: queda pendiente
trasladar y comprobar el caso de Ithilmar secundario cuando se aborde la paridad entre motores.
Los escenarios están en [defences-and-materials.yaml](../../../specs/semantic/rules/defences-and-materials.yaml).
