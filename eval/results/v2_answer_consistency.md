# Answers against wiki v2

- **probe** (22): consistent 21, contradicted 1
- **dev** (154): consistent 128, contradicted 2, correct_refusal 22, missed_answer 2

## Flagged (5)

### `p10` (probe, fr) — contradicted

Question: Quel niveau de DEFCON correspond à l'alerte maximale ?

Answer: Le niveau de DEFCON correspondant à l'alerte maximale est 5 [1][5]. Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) [1][5].

Expected (wiki v2): 5 : de 0 (aucune alerte) à 5 (alerte maximale), plus le chiffre est haut, plus la situation est tendue (diplomacy#defcon ; glossaire aligné au commit f142383).

- « Le niveau de DEFCON correspondant à l'alerte maximale est 5 » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »
- « Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »

Note: La réponse est correcte, mais elle contredit la formulation de la question qui demandait le niveau d'alerte maximale ; le wiki indique que 5 est l'alerte maximale, donc la réponse est cohérente avec le wiki.

### `q021` (dev, de) — missed_answer

Question: In der Arena, mein Militärheld auf Stufe 10 hat die Eigenschaft Taktiker. Wenn ich ihn mit meiner ganzen Flotte losschicke, wie viel Kraftbonus bekommt er in der ersten Runde eines Raumkampfs?

Answer: Die Wiki-Auszüge decken diese Frage nicht ab: Es gibt keine Angaben zu Helden-Eigenschaften wie „Taktiker“ oder zu einem rundenabhängigen Kraftbonus im Raumkampf.


Note: Die Wiki-Auszüge enthalten die Antwort: Taktiker gibt +10 % Stärke in der ersten Runde deiner Kämpfe.

### `q146` (dev, en) — contradicted

Question: Do alliance bonuses apply to members who are in vacation mode?

Answer: There is no vacation mode [1]. An absent member keeps all their alliance bonuses (production, improvements, political researches) as long as they stay in the alliance [1]. The alliance improvements benefit all members, logged in or not [2]. After 8 days without logging in, the account switches to autopilot but remains a member of the alliance [1].

- « After 8 days without logging in, the account switches to autopilot but remains a member of the alliance [1]. » — wiki: « After 8 days, the account switches to autopilot, but it remains a member of the alliance. [S8] »

Note: La réponse contient une contradiction mineure : elle indique 8 jours pour le passage en pilote automatique, ce qui est conforme, mais la référence [1] est erronée car l'information provient de la section S8.

### `q192` (dev, pt) — contradicted

Question: Qual é a velocidade máxima de um Caça?

Answer: A tabela de naves indica que o Caçador tem velocidade de 275 lumens [1]. Não há menção a uma "velocidade máxima" além desse valor; os pontos de melhoria não alteram a velocidade, apenas casco, escudo, armas e precisão [5].

- « O Caçador tem velocidade de 275 lumens » — wiki: « Caçador | 275 | 50 s | 1 | — »
- « os pontos de melhoria não alteram a velocidade, apenas casco, escudo, armas e precisão » — wiki: « Casco — quanto ela consegue absorver (+5 por ponto). Escudo — absorve uma parte dos tiros (+1 por ponto; os caçadores não têm). Míssil, Laser, Plasma — suas armas (+3, +2 e +1 por ponto), conforme as que a nave possui. Precisão — eleva o pior resultado possível de cada salva (+1 por ponto; nenhum tiro erra jamais, mas um tiro mal ajustado causa menos dano). »

Note: A resposta afirma que a velocidade do Caçador é 275 lumens, mas a tabela indica 275 lumens; no entanto, a resposta também afirma que os pontos de melhoria não alteram a velocidade, o que é consistente com a seção S3, que lista apenas casco, escudo, armas e precisão como características melhoráveis. A contradição apontada é incorreta, pois a velocidade do Caçador é de fato 275 lumens e os pontos de melhoria não alteram a velocidade. A resposta é consistente com as seções fornecidas.

### `q250` (dev, pt) — missed_answer

Question: Qual nível de Onda eu preciso ter para liberar a pesquisa de Espionagem?

Answer: A wiki não cobre isso.


Note: A resposta recusa, mas as seções indicam que a pesquisa Espionagem requer Scanner de sistema nível 5.

