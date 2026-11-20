# Answers against wiki v2

- **probe** (19): consistent 18, contradicted 1
- **dev** (154): consistent 128, contradicted 1, correct_refusal 23, missed_answer 2

## Flagged (4)

### `p10` (probe, fr) — contradicted

Question: Quel niveau de DEFCON correspond à l'alerte maximale ?

Answer: Le niveau de DEFCON correspondant à l'alerte maximale est 5 [1][5]. Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) [1][5].

Expected (wiki v2): 5 : de 0 (aucune alerte) à 5 (alerte maximale), plus le chiffre est haut, plus la situation est tendue (diplomacy#defcon ; glossaire aligné au commit f142383).

- « Le niveau de DEFCON correspondant à l'alerte maximale est 5 » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »
- « Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »

Note: La réponse est correcte, mais elle contredit la formulation de la question qui demandait le niveau d'alerte maximale ; le wiki indique que 5 est l'alerte maximale, donc la réponse est cohérente avec le wiki.

### `q021` (dev, de) — missed_answer

Question: In der Arena, mein Militärheld auf Stufe 10 hat die Eigenschaft Taktiker. Wenn ich ihn mit meiner ganzen Flotte losschicke, wie viel Kraftbonus bekommt er in der ersten Runde eines Raumkampfs?

Answer: Die Wiki-Auszüge decken diese Frage nicht ab: Es gibt keine Angaben zu Heldenstufen, zur Eigenschaft „Taktiker“ oder zu einem rundenweisen Kraftbonus im Raumkampf.


Note: La réponse refuse à tort : les sections S7 et S8 indiquent que la propriété Tacticien donne +10 % de force au premier tour des combats, y compris dans l'arène.

### `q027` (dev, es) — contradicted

Question: ¿Qué significa el DEFCON 1 para una alianza en Area Universe?

Answer: El DEFCON es el nivel de alerta de tu alianza, de 0 a 5: cuanto más alta es la cifra, más tensa es la situación, siendo 0 ninguna alerta y 5 alerta máxima [1]. Por tanto, el DEFCON 1 es un nivel de alerta bajo, el primero por encima de «ninguna alerta» [1]. Se muestra como un banner en la Vista general de todos los miembros, verde en 1, junto a la lista de alianzas con las que estás en guerra [1]. Es una señal de coordinación, sin efecto en los combates [1]. Lo ajusta un miembro con el permiso Modificar en la pestaña Administración («Nivel de defensa») [1].

- « El DEFCON es el nivel de alerta de tu alianza, de 0 a 5: cuanto más alta es la cifra, más tensa es la situación, siendo 0 ninguna alerta y 5 alerta máxima » — wiki: « Tu alianza tiene un nivel de alerta DEFCON, de 0 a 5: cuanto más alta es la cifra, más tensa es la situación. 0 = ninguna alerta, 5 = alerta máxima. »
- « Por tanto, el DEFCON 1 es un nivel de alerta bajo, el primero por encima de «ninguna alerta» » — wiki: « El nivel se muestra como un banner en la Vista general de todos los miembros (verde en 1, naranja en 2, rojo de 3 a 5, nada en 0) »
- « Se muestra como un banner en la Vista general de todos los miembros, verde en 1, junto a la lista de alianzas con las que estás en guerra » — wiki: « El nivel se muestra como un banner en la Vista general de todos los miembros (verde en 1, naranja en 2, rojo de 3 a 5, nada en 0), con la lista de las alianzas con las que estás en guerra. »
- « Es una señal de coordinación, sin efecto en los combates » — wiki: « Es una señal de coordinación, sin efecto en los combates. »
- « Lo ajusta un miembro con el permiso Modificar en la pestaña Administración («Nivel de defensa») » — wiki: « Un miembro que tenga el permiso Modificar lo ajusta en la pestaña Administración («Nivel de defensa»). »

Note: La respuesta contradice la wiki al afirmar que el DEFCON 1 es un nivel de alerta bajo, cuando la wiki indica que es el nivel más bajo después de 0, pero no especifica que sea 'bajo' en términos de tensión; además, la wiki menciona que una declaración de guerra pone automáticamente a las dos alianzas en DEFCON 5, lo cual no se menciona en la respuesta.

### `q250` (dev, pt) — missed_answer

Question: Qual nível de Onda eu preciso ter para liberar a pesquisa de Espionagem?

Answer: A wiki não cobre isso.


Note: A resposta recusa, mas as seções indicam que a pesquisa Espionagem requer Scanner de sistema nível 5.

