# Answers against wiki v2

- **probe** (18): consistent 15, contradicted 1, correct_refusal 2
- **dev** (154): consistent 127, contradicted 2, correct_refusal 23, missed_answer 2

## Flagged (5)

### `p10` (probe, fr) — contradicted

Question: Quel niveau de DEFCON correspond à l'alerte maximale ?

Answer: Le niveau de DEFCON correspondant à l'alerte maximale est 5 [1][5]. Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) [1][5].

Expected (wiki v2): 5 : de 0 (aucune alerte) à 5 (alerte maximale), plus le chiffre est haut, plus la situation est tendue (diplomacy#defcon ; glossaire aligné au commit f142383).

- « Le niveau de DEFCON correspondant à l'alerte maximale est 5 » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »
- « Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »

Note: La réponse est correcte selon les sections du wiki.

### `q021` (dev, de) — missed_answer

Question: In der Arena, mein Militärheld auf Stufe 10 hat die Eigenschaft Taktiker. Wenn ich ihn mit meiner ganzen Flotte losschicke, wie viel Kraftbonus bekommt er in der ersten Runde eines Raumkampfs?

Answer: Die Wiki-Auszüge decken diese Frage nicht ab: Es gibt keine Angaben zu Heldenstufen, zur Eigenschaft „Taktiker“ oder zu einem rundenweisen Kraftbonus im Raumkampf.


Note: La réponse refuse à tort : les sections S7 et S8 indiquent que la propriété Tacticien donne +10 % de force au premier tour des combats, y compris dans l'arène.

### `q027` (dev, es) — contradicted

Question: ¿Qué significa el DEFCON 1 para una alianza en Area Universe?

Answer: El DEFCON es el nivel de alerta de tu alianza, de 0 a 5: cuanto más alta es la cifra, más tensa es la situación [1]. El DEFCON 1 corresponde a un nivel bajo de alerta y se muestra como un banner verde en la Vista general de todos los miembros [1]. Es una señal de coordinación y no tiene efecto en los combates [1]. Una declaración de guerra pone automáticamente a las dos alianzas en DEFCON 5 [1].

- « El DEFCON 1 corresponde a un nivel bajo de alerta » — wiki: « cuanto más alta es la cifra, más tensa es la situación. 0 = ninguna alerta, 5 = alerta máxima »

Note: El DEFCON 1 no es un nivel bajo de alerta; es un nivel intermedio, ya que 0 es ninguna alerta y 5 es alerta máxima.

### `q089` (dev, es) — contradicted

Question: ¿Cuántos legionarios puede llevar una barcaza sin contar las investigaciones de alianza?

Answer: Una barcaza transporta 1 000 Legionarios de base [1]. Ese número aumenta +25 % por nivel de la investigación política «Invasiones planificadas» (1 250 en el nivel 1, 1 500 en el nivel 2…) [1], que es una investigación política, no de alianza [3][4]. Si tienes más Legionarios que plazas, los excedentes se quedan en órbita y no combaten [1].

- « que es una investigación política, no de alianza [3][4] » — wiki: « Invasiones planificadas (niv. 2) | +25 % de capacidad de las barcazas por nivel: 1 250 Legionarios por barcaza en el nivel 1, 2 250 en el nivel 5 »

Note: La investigación «Invasiones planificadas» aparece en la tabla de investigaciones de alianza del régimen El Martillo de las Estrellas, por lo que sí es una investigación de alianza.

### `q250` (dev, pt) — missed_answer

Question: Qual nível de Onda eu preciso ter para liberar a pesquisa de Espionagem?

Answer: A wiki não cobre isso.


Note: A resposta recusa, mas as seções indicam que a pesquisa Espionagem requer Scanner de sistema nível 5.

