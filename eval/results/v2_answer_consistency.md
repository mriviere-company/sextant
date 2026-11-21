# Answers against wiki v2

- **probe** (24): consistent 22, contradicted 2
- **dev** (154): consistent 127, contradicted 2, correct_refusal 24, missed_answer 1

## Flagged (5)

### `p10` (probe, fr) — contradicted

Question: Quel niveau de DEFCON correspond à l'alerte maximale ?

Answer: Le niveau de DEFCON correspondant à l'alerte maximale est 5 [1][5]. Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) [1][5].

Expected (wiki v2): 5 : de 0 (aucune alerte) à 5 (alerte maximale), plus le chiffre est haut, plus la situation est tendue (diplomacy#defcon ; glossaire aligné au commit f142383).

- « Le niveau de DEFCON correspondant à l'alerte maximale est 5 » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »
- « Le DEFCON va de 0 (aucune alerte) à 5 (alerte maximale) » — wiki: « DEFCON | Niveau d'alerte d'alliance, de 0 (aucune alerte) à 5 (alerte maximale) »

Note: La réponse est correcte, mais elle contredit la formulation de la question qui demandait le niveau d'alerte maximale ; le wiki indique que 5 est l'alerte maximale, donc la réponse est cohérente avec le wiki.

### `p23` (probe, es) — contradicted

Question: Mis trabajadores producen 50 000 Bitcoins al día. Mi alianza tiene un impuesto del 10 % y además paga un impuesto de paz del 20 % por una paz perdida. ¿Cuánto me quita el impuesto de alianza?

Answer: El impuesto de paz del 20 % se descuenta primero del ingreso de tus trabajadores, y el impuesto de alianza se aplica después sobre lo que queda [2]. Sobre 50 000 Bitcoins, el impuesto de paz retira 10 000 (20 %), dejando 40 000 [5]. Con una tasa del 10 %, la parte descontada vale ingreso × t ÷ (100 + t), es decir, aproximadamente un 9 % del ingreso [2]; sobre 40 000, el impuesto de alianza te quita unos 3 636 Bitcoins [2]. El descuento se hace automáticamente en el informe diario (18:59, hora de París) y se ingresa en la tesorería de la alianza [1].

Expected (wiki v2): La taxe de paix d'abord (20 % de 50 000 = 10 000), puis la taxe d'alliance sur le reste : 40 000 × 10 ÷ 110 ≈ 3 636 (daily_report#contenu, 99afafd2). Calculée sur le brut, elle donnerait ≈ 4 545 : faux.

- « El impuesto de paz del 20 % se descuenta primero del ingreso de tus trabajadores, y el impuesto de alianza se aplica después sobre lo que queda » — wiki: « Impuesto de paz — ... ese porcentaje se descuenta del ingreso de tus trabajadores. Impuesto de alianza — descontado del ingreso de tus trabajadores (después del impuesto de paz, si lo hay) »
- « Sobre 50 000 Bitcoins, el impuesto de paz retira 10 000 (20 %), dejando 40 000 » — wiki: « Ejemplo: al 20 %, un miembro que cobra 10 000 Bitcoins al día revierte 2 000. »
- « sobre 40 000, el impuesto de alianza te quita unos 3 636 Bitcoins » — wiki: « Cálculo: el descuento vale ingreso − ingreso ÷ (1 + tasa). Un impuesto del 10 % retira, pues, alrededor del 9,1 % del ingreso »

Note: Le calcul de l'impôt d'alliance est basé sur le revenu après impôt de paix, mais le montant exact diffère de la réponse.

### `q021` (dev, de) — missed_answer

Question: In der Arena, mein Militärheld auf Stufe 10 hat die Eigenschaft Taktiker. Wenn ich ihn mit meiner ganzen Flotte losschicke, wie viel Kraftbonus bekommt er in der ersten Runde eines Raumkampfs?

Answer: Die Wiki-Auszüge decken diese Frage nicht ab: Es gibt keine Angaben zu Helden-Eigenschaften wie „Taktiker“ oder zu einem rundenabhängigen Kraftbonus im Raumkampf.


Note: Die Wiki-Auszüge enthalten die Antwort: Taktiker gibt +10 % Stärke in der ersten Runde deiner Kämpfe.

### `q060` (dev, fr) — contradicted

Question: Différence récompenses classement Alliance vs Arène héros ?

Answer: Les extraits ne décrivent pas de « classement Alliance » ni de « classement Arène héros ». Ils couvrent les récompenses de l'Arène Alliance [2] : la banque alliance reçoit selon le tour atteint 50 000 à 1 000 000 Bitcoins et 1 000 à 25 000 PDG [2], plus les PDG des planètes tenues [2] ; le bonus individuel va de 5 000 à 50 000 Bitcoins personnels, à condition d'avoir donné au moins un ordre [2]. Pour l'Arène PvP, les extraits mentionnent un classement par serveur des duellistes avec récompenses hebdomadaires (top 3 : uranium et PDG) [5], mais pas de récompenses de tournoi détaillées [3]. La comparaison demandée n'est donc pas couverte.

- « le bonus individuel va de 5 000 à 50 000 Bitcoins personnels, à condition d'avoir donné au moins un ordre » — wiki: « Bonus individuel ... à condition d'avoir donné au moins un ordre vous-même pendant l'un des matchs de la soirée ... Perdants tour 1 | 5 000 ... Champion | 50 000 »
- « Pour l'Arène PvP, les extraits mentionnent un classement par serveur des duellistes avec récompenses hebdomadaires (top 3 : uranium et PDG) [5], mais pas de récompenses de tournoi détaillées [3] » — wiki: « Récompenses : 1er = 5000 uranium + 500 PDG + 1 item épique ... 2ème = 3000 uranium + 300 PDG + 1 item rare ... 3ème = 1500 uranium + 150 PDG + 1 item rare ... Autres participants = 500 uranium + 50 PDG »

Note: La réponse contredit les sections sur les récompenses de tournoi de l'Arène PvP et omet des détails.

### `q192` (dev, pt) — contradicted

Question: Qual é a velocidade máxima de um Caça?

Answer: A tabela de naves indica que o Caçador tem velocidade de 275 lumens [1]. Não há menção a uma velocidade máxima diferente para ele; a velocidade é dada em lumens, quanto mais alta, mais rápida a nave [1].

- « O Caçador tem velocidade de 275 lumens » — wiki: « Caçador | 275 | 50 s | 1 | — »

Note: A velocidade de 275 lumens está correta, mas a pergunta era sobre a velocidade máxima de um Caça, e a resposta não menciona que não há uma velocidade máxima diferente; a velocidade é fixa em 275 lumens.

