# Answers against wiki v2

- **probe** (24): consistent 22, contradicted 2
- **dev** (154): consistent 128, contradicted 2, correct_refusal 22, missed_answer 2

## Flagged (6)

### `p10` (probe, fr) — contradicted

Question: Quel niveau de DEFCON correspond à l'alerte maximale ?

Answer: L'alerte maximale correspond au niveau DEFCON 5 [1][5]. Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) [1][5], et une déclaration de guerre place automatiquement les deux alliances à DEFCON 5 [1].

Expected (wiki v2): 5 : de 0 (aucune alerte) à 5 (alerte maximale), plus le chiffre est haut, plus la situation est tendue (diplomacy#defcon ; glossaire aligné au commit f142383).

- « L'alerte maximale correspond au niveau DEFCON 5 » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »
- « Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »
- « une déclaration de guerre place automatiquement les deux alliances à DEFCON 5 » — wiki: « Une déclaration de guerre met automatiquement les deux alliances à DEFCON 5. »

Note: La réponse est correcte et conforme aux sections du wiki.

### `p22` (probe, pt) — contradicted

Question: A venda com um clique na página Planetas também dá Pontos de Guerra?

Answer: Não. A venda aos mercadores pela aba Venda aos mercadores da página Planetas é feita na hora, sem cargueiro nem combustível, mas 20 % mais barata do que entregando você mesmo (0,10 Bitcoin por niobium, 0,25 por água) e sem Pontos de Guerra [2]. Os PDG são ganhos em combate espacial, defesa orbital, raid, invasão e na venda aos mercadores, com bônus da pesquisa de aliança Pontos de Guerra [3].

Expected (wiki v2): Non : 0,10 Bitcoin par niobium et 0,25 par eau, aucun PDG ; seules les ventes livrées par une flotte en rapportent (market, 9a80d9d2).

- « Os PDG são ganhos em combate espacial, defesa orbital, raid, invasão e na venda aos mercadores, com bônus da pesquisa de aliança Pontos de Guerra [3]. » — wiki: « A pesquisa de aliança Pontos de Guerra (aliança de nível 6 no mínimo) aumenta em 10 % por nível, até +50 %, os PDG ganhos em combate espacial, em defesa orbital, em raid, em invasão e na venda aos mercadores. »

Note: A resposta afirma que a venda com um clique não dá PDG, o que está correto, mas a citação sobre os PDG ganhos na venda aos mercadores é ambígua e pode induzir a erro, pois a venda com um clique não dá PDG, apenas a venda entregue por frota.

### `q021` (dev, de) — missed_answer

Question: In der Arena, mein Militärheld auf Stufe 10 hat die Eigenschaft Taktiker. Wenn ich ihn mit meiner ganzen Flotte losschicke, wie viel Kraftbonus bekommt er in der ersten Runde eines Raumkampfs?

Answer: Die Wiki-Auszüge decken diese Frage nicht ab: Es gibt keine Angaben zu Helden-Eigenschaften wie „Taktiker“ oder zu einem rundenabhängigen Kraftbonus im Raumkampf.


Note: Die Wiki-Auszüge enthalten die Antwort: Taktiker gibt +10 % Stärke in der ersten Runde deiner Kämpfe.

### `q027` (dev, es) — contradicted

Question: ¿Qué significa el DEFCON 1 para una alianza en Area Universe?

Answer: El DEFCON es el nivel de alerta de tu alianza, de 0 a 5: cuanto más alta es la cifra, más tensa es la situación, siendo 0 ninguna alerta y 5 alerta máxima [1]. Por tanto, el DEFCON 1 es un nivel de alerta bajo, el primero por encima de 0, y se muestra como un banner verde en la Vista general de todos los miembros, junto a la lista de alianzas con las que estás en guerra [1]. Es solo una señal de coordinación, sin efecto en los combates [1]. Lo ajusta un miembro con el permiso Modificar en la pestaña Administración («Nivel de defensa») [1].

- « el DEFCON 1 es un nivel de alerta bajo, el primero por encima de 0 » — wiki: « 0 = ninguna alerta, 5 = alerta máxima »
- « se muestra como un banner verde en la Vista general de todos los miembros » — wiki: « verde en 1, naranja en 2, rojo de 3 a 5, nada en 0 »

Note: La respuesta describe correctamente el DEFCON 1 como un nivel bajo y verde, pero contradice la escala al afirmar que es el primer nivel por encima de 0, cuando la wiki indica que 0 es ninguna alerta y 5 es máxima.

### `q146` (dev, en) — contradicted

Question: Do alliance bonuses apply to members who are in vacation mode?

Answer: There is no vacation mode [1]. An absent member keeps all their alliance bonuses (production, improvements, political researches) as long as they stay in the alliance [1]. The alliance improvements benefit all members, logged in or not [2]. After 8 days without logging in, the account switches to autopilot but remains a member of the alliance [1].

- « After 8 days without logging in, the account switches to autopilot but remains a member of the alliance [1]. » — wiki: « After 8 days, the account switches to autopilot, but it remains a member of the alliance. [S8] »

Note: La réponse contient une contradiction mineure : elle indique 8 jours pour le passage en pilote automatique, ce qui est conforme, mais la référence [1] est erronée car l'information provient de la section S8.

### `q250` (dev, pt) — missed_answer

Question: Qual nível de Onda eu preciso ter para liberar a pesquisa de Espionagem?

Answer: A wiki não cobre isso.


Note: A resposta recusa, mas as seções indicam que a pesquisa Espionagem requer Scanner de sistema nível 5.

