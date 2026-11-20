# Judges: deepseek-flash against deepseek-v4-pro (dev split)

Protocol and rule: [`eval/LLM_MODELS.md`](../LLM_MODELS.md). Rule: a judge switches to flash if kappa ≥ 0.80 on every decision it feeds to code.

| Judge | Items | Decision | Units | Kappa | 95 % CI | Agreement | Flash? |
|---|---|---|---|---|---|---|---|
| relevance_judge | 144 | section | 4058 | 0.805 | 0.751 to 0.857 | 97.3% | yes |
| relevance_judge | 144 | answerable | 144 | 0.911 | 0.790 to 1.000 | 97.9% | yes |
| reassessment | 144 | old_answer | 144 | 0.536 | 0.435 to 0.635 | 69.4% | no |
| reassessment | 144 | answerable | 144 | 0.664 | 0.000 to 1.000 | 99.3% | no |
| reassessment | 144 | question_valid | 144 | -0.011 | -0.027 to 0.000 | 96.5% | no |
| strict_check | 45 | consistent | 45 | 0.604 | 0.328 to 0.835 | 84.4% | no |

## Models chosen

- `draft`: `deepseek-flash`
- `relevance_judge`: `deepseek-flash`
- `reassessment`: `deepseek-v4-pro`
- `strict_check`: `deepseek-v4-pro`
- `answer_judge`: `deepseek-v4-pro`

Flash replay: 333 calls, 2672325 input and 54369 output tokens, about 0.43 $ (price at run time). Unusable answers (not JSON after a retry): relevance_judge pro 0 / flash 0, reassessment pro 0 / flash 0, strict_check pro 0 / flash 0.

## Disagreements

### relevance_judge (112)

- answerable: yes->no: 3
- section: no->yes: 83
- section: yes->no: 26

- q001 `section` — S7 Glossary — All game terms: pro no, flash yes
- q001 `section` — S19 Moons — How to create a moon: pro no, flash yes
- q003 `section` — S14 Tesorería de alianza — Para qué sirve la tesorería: pro no, flash yes
- q003 `section` — S18 Investigaciones de alianza — Cómo funciona: pro no, flash yes
- q021 `section` — S4 Weltraumkampf — Die Stärke einer Seite: pro yes, flash no
- q025 `section` — S3 Glossaire — Tous les termes du jeu: pro yes, flash no
- q025 `section` — S17 Tout ce qu'on trouve sur la carte — Cas particulier : les lunes: pro yes, flash no
- q030 `section` — S2 Créer sa première flotte — Étape 2 — Composer et envoyer une flotte: pro no, flash yes
- q031 `section` — S26 Достижения — 15 достижений: pro yes, flash no
- q038 `section` — S1 Create your first fleet — Good ships to start with: pro no, flash yes
- q038 `section` — S7 Ship types — Utility ships: pro no, flash yes
- q038 `section` — S8 Mission types — Available types: pro no, flash yes
- q049 `section` — S24 Les prophéties de Cthulhu — L'annonce: pro yes, flash no
- q051 `section` — S18 Настройка Ваших кораблей — Режимы серверов с максимальными исследованиями: pro no, flash yes
- q051 `section` — S21 Понимание мощности войск — Точность и броски боя: pro no, flash yes
- q073 `section` — S9 Космический бой — Когда начинается бой: pro no, flash yes
- q078 `section` — S3 Space combat — When a battle starts: pro no, flash yes
- q081 `section` — S12 Защита планет — Тактическое развёртывание: pro no, flash yes
- q082 `section` — S3 Bitcoins y mantenimiento — ¿Cómo ganarlos?: pro no, flash yes
- q082 `section` — S7 Glosario — Todos los términos del juego: pro no, flash yes
- q082 `section` — S8 Trabajadores y científicos — Los trabajadores: pro no, flash yes
- q083 `section` — S1 Игровые отчёты — Отчёты о бое: pro yes, flash no
- q083 `section` — S2 Глоссарий — Все игровые термины: pro yes, flash no
- q083 `section` — S18 Читаем отчёт о бое — Типы боевых отчётов: pro yes, flash no
- q090 `section` — S12 Embargo and famine — The principle: pro no, flash yes
- q090 `section` — S13 Embargo and famine — Reminder: food: pro no, flash yes
- q093 `section` — S14 Создать и вступить в альянс — 3 политических режима: pro no, flash yes
- q093 `section` — S19 3 политических режима — Безмолвный Оплот (наступательный): pro no, flash yes
- q095 `section` — S10 Создать и отправить флот — Этап 3 — Отправить флот: pro no, flash yes
- q095 `section` — S11 Типы миссий — Принцип: pro no, flash yes
- q096 `section` — S10 Personalizar suas naves — O princípio: pro no, flash yes
- q096 `section` — S11 Personalizar suas naves — Como usá-los: pro no, flash yes
- q096 `section` — S12 Personalizar suas naves — Ler a sua mira no ecrã: pro no, flash yes
- q096 `section` — S14 Personalizar suas naves — Modos de servidor com pesquisas máximas: pro no, flash yes
- q096 `section` — S19 Entendendo a potência das tropas — Precisão e lançamentos de combate: pro no, flash yes
- q096 `section` — S22 Os modos de servidor — Modos com pesquisas máximas desde o início: pro no, flash yes
- q101 `section` — S8 Forschung und Technologien — Vollständige Liste der Forschungen: pro no, flash yes
- q108 `section` — S3 Votre premier combat — Ce qui se passe étape par étape: pro yes, flash no
- q108 `section` — S12 Invasion de planète — Phase 1 — Combat en orbite (parfois): pro yes, flash no
- q108 `section` — S32 Arène Alliance — Ta flotte: pro yes, flash no
- q115 `section` — S17 Tesorería de alianza — Para qué sirve la tesorería: pro no, flash yes
- q118 `section` — S1 Space combat — After the battle: pro no, flash yes
- q118 `section` — S2 Planet invasion — If you win the invasion: pro no, flash yes
- q124 `section` — S6 Criar sua primeira frota — Ideia de primeira missão: pro yes, flash no
- q128 `section` — S10 Héroes secundarios — Ninguna recuperación posible: pro yes, flash no
- q140 `section` — S25 Excluir a minha conta e os meus dados — Onde solicitar: pro yes, flash no
- q140 `section` — S26 Excluir a minha conta e os meus dados — Um abandono de conta definitivo: pro yes, flash no
- q140 `section` — S27 Excluir a minha conta e os meus dados — O que é conservado, e por quê: pro yes, flash no
- q140 `answerable`: pro yes, flash no
- q144 `section` — S21 Einen Planeten aufgeben — Wie es geht: pro yes, flash no
- q148 `section` — S4 Советы для успешного старта — Военное дело: pro no, flash yes
- q148 `section` — S11 Настройка Ваших кораблей — Как читать наведение на экране: pro yes, flash no
- q148 `section` — S13 Настройка Ваших кораблей — Советы: pro yes, flash no
- q151 `section` — S26 Улучшения альянса — Уровни и пороги: pro no, flash yes
- q158 `section` — S5 Les rapports du jeu — Rapports de combat: pro yes, flash no
- q158 `section` — S10 Lire un rapport de combat — Types de rapports de combat: pro yes, flash no
- q160 `section` — S33 Améliorations d'alliance — Les 16 bonus et leurs effets: pro no, flash yes
- q164 `section` — S22 Альянсовая арена — Когда стартует: pro no, flash yes
- q164 `section` — S23 Альянсовая арена — Как зарегистрироваться: pro no, flash yes
- q165 `section` — S3 Bitcoins e manutenção — Como ganhar?: pro no, flash yes
- q165 `section` — S4 Bitcoins e manutenção — A manutenção diária: pro no, flash yes
- q165 `section` — S17 O relatório diário — O que o relatório contém: pro no, flash yes
- q166 `section` — S4 Crear tu primera flota — Paso 2 — Componer y enviar una flota: pro no, flash yes
- q166 `section` — S14 Crear y enviar una flota — Paso 3 — Enviar la flota: pro no, flash yes
- q183 `section` — S24 The 3 political regimes — Bonuses between regimes: pro yes, flash no
- q193 `section` — S8 Космический бой — Когда начинается бой: pro no, flash yes
- q193 `section` — S22 Защита планет — Ваша оборона стреляет и без режима атаки: pro no, flash yes
- q202 `section` — S20 Navegando na galáxia — Ler uma coordenada: pro yes, flash no
- q205 `section` — S2 Criar e entrar em uma aliança — Por que entrar em uma aliança?: pro yes, flash no
- q228 `section` — S22 Eliminar mi cuenta y mis datos — Dónde solicitarlo: pro no, flash yes
- q230 `section` — S1 Primeros pasos — A vigilar desde el principio: pro no, flash yes
- q230 `section` — S5 Tu primer combate — Después del combate: pro no, flash yes
- q230 `section` — S14 Invasión de planeta — Eliminación del defensor: pro no, flash yes
- q230 `section` — S16 Defender tus planetas — Activar el modo ataque de tu planeta: pro no, flash yes
- q230 `section` — S25 Puntos de Guerra (PDG) — ¿Qué son los PDG?: pro no, flash yes
- q230 `section` — S35 Arena Alianza — Planetas y puntos: pro no, flash yes
- q232 `section` — S3 Your first combat — After the fight: pro no, flash yes
- q232 `section` — S8 Space combat — After the battle: pro no, flash yes
- q232 `section` — S16 War Points (WP) — What are WP?: pro no, flash yes
- q232 `section` — S17 War Points (WP) — How to earn them: pro no, flash yes
- q232 `section` — S18 War Points (WP) — What they're for: pro no, flash yes
- q232 `section` — S19 War Points (WP) — Strategy: pro no, flash yes
- q232 `section` — S22 PvP Arena — Base rewards: pro no, flash yes
- q236 `section` — S11 Эмбарго и голод — Как противостоять эмбарго: pro no, flash yes
- q237 `section` — S3 Criar sua primeira frota — As boas naves para começar: pro no, flash yes
- q237 `section` — S8 Pesquisa e tecnologias — Prioridades para um iniciante: pro no, flash yes
- q237 `section` — S16 Criar e enviar uma frota — Etapa 3 — Enviar a frota: pro no, flash yes
- q237 `section` — S18 Tipos de missões — Os tipos disponíveis: pro no, flash yes
- q237 `section` — S19 Tipos de missões — Como escolher a missão certa: pro no, flash yes
- q245 `section` — S14 Embargo und Hungersnot — Das Prinzip: pro no, flash yes
- q246 `section` — S16 The 3 political regimes — The Balance of Worlds (democratic): pro no, flash yes
- q254 `section` — S15 Types de missions — Les types disponibles: pro yes, flash no
- q257 `section` — S2 Glossary — All game terms: pro yes, flash no
- q257 `section` — S5 Mission types — How to pick the right mission: pro no, flash yes
- q261 `section` — S24 Alliance Arena — How it works: pro no, flash yes
- q264 `section` — S1 Primeros pasos — Tus 6 primeras acciones: pro no, flash yes
- q264 `section` — S9 Mercado y comerciantes — ¿Quiénes son los comerciantes?: pro no, flash yes
- q264 `section` — S10 Mercado y comerciantes — Cómo venderles: pro no, flash yes
- q271 `section` — S1 Первые шаги — Ваши 6 первых действий: pro no, flash yes
- q271 `section` — S4 Биткойны и содержание — Как их зарабатывать?: pro no, flash yes
- q271 `section` — S5 Создание первого флота — Подходящие корабли для старта: pro no, flash yes
- q271 `section` — S11 Рынок и торговцы — Кто такие торговцы?: pro no, flash yes
- q271 `section` — S19 Типы миссий — Доступные типы: pro no, flash yes
- q271 `section` — S20 Типы миссий — Как выбрать правильную миссию: pro no, flash yes
- q271 `section` — S21 Всё, что можно найти на карте — 7 типов объектов: pro no, flash yes
- q271 `section` — S24 Ежедневные задания — Примеры заданий: pro no, flash yes
- q272 `answerable`: pro yes, flash no
- q276 `answerable`: pro yes, flash no
- q278 `section` — S20 Allianzschatzkammer — Die Abhebungen: pro no, flash yes
- q280 `section` — S15 Trocas entre jogadores — O princípio: pro no, flash yes
- q280 `section` — S16 Trocas entre jogadores — Enviar recursos físicos: pro no, flash yes
- q281 `section` — S13 Intercambios entre jugadores — El principio: pro no, flash yes

### reassessment (50)

- answerable: no->yes: 1
- old_answer: consistent->contradicted: 10
- old_answer: consistent->incomplete: 23
- old_answer: contradicted->consistent: 1
- old_answer: contradicted->incomplete: 3
- old_answer: contradicted->not_applicable: 3
- old_answer: incomplete->contradicted: 3
- old_answer: not_applicable->contradicted: 1
- question_valid: no->yes: 1
- question_valid: yes->no: 4

- q003 `old_answer`: pro consistent, flash contradicted
- q007 `old_answer`: pro incomplete, flash contradicted
- q014 `old_answer`: pro consistent, flash contradicted
- q020 `old_answer`: pro consistent, flash incomplete
- q021 `old_answer`: pro consistent, flash incomplete
- q024 `old_answer`: pro consistent, flash contradicted
- q024 `question_valid`: pro yes, flash no
- q025 `old_answer`: pro consistent, flash incomplete
- q043 `old_answer`: pro consistent, flash contradicted
- q045 `old_answer`: pro contradicted, flash not_applicable
- q050 `old_answer`: pro consistent, flash incomplete
- q052 `old_answer`: pro consistent, flash incomplete
- q054 `old_answer`: pro contradicted, flash incomplete
- q055 `old_answer`: pro consistent, flash incomplete
- q069 `old_answer`: pro consistent, flash incomplete
- q074 `old_answer`: pro consistent, flash incomplete
- q077 `old_answer`: pro consistent, flash incomplete
- q090 `old_answer`: pro consistent, flash incomplete
- q094 `old_answer`: pro consistent, flash incomplete
- q108 `old_answer`: pro contradicted, flash not_applicable
- q119 `old_answer`: pro consistent, flash incomplete
- q124 `old_answer`: pro consistent, flash incomplete
- q125 `old_answer`: pro consistent, flash incomplete
- q142 `old_answer`: pro consistent, flash incomplete
- q146 `old_answer`: pro contradicted, flash not_applicable
- q146 `question_valid`: pro yes, flash no
- q151 `old_answer`: pro consistent, flash incomplete
- q152 `old_answer`: pro consistent, flash contradicted
- q155 `old_answer`: pro consistent, flash incomplete
- q157 `old_answer`: pro not_applicable, flash contradicted
- q157 `answerable`: pro no, flash yes
- q157 `question_valid`: pro no, flash yes
- q159 `old_answer`: pro consistent, flash contradicted
- q161 `old_answer`: pro consistent, flash incomplete
- q166 `old_answer`: pro incomplete, flash contradicted
- q184 `old_answer`: pro contradicted, flash consistent
- q190 `old_answer`: pro consistent, flash incomplete
- q206 `old_answer`: pro consistent, flash incomplete
- q208 `old_answer`: pro incomplete, flash contradicted
- q210 `old_answer`: pro consistent, flash contradicted
- q213 `old_answer`: pro consistent, flash contradicted
- q220 `question_valid`: pro yes, flash no
- q222 `old_answer`: pro contradicted, flash incomplete
- q240 `old_answer`: pro consistent, flash incomplete
- q244 `old_answer`: pro contradicted, flash incomplete
- q254 `question_valid`: pro yes, flash no
- q255 `old_answer`: pro consistent, flash contradicted
- q261 `old_answer`: pro consistent, flash contradicted
- q278 `old_answer`: pro consistent, flash incomplete
- q281 `old_answer`: pro consistent, flash incomplete

### strict_check (7)

- consistent: yes->no: 7

- q021 `consistent`: pro yes, flash no
- q043 `consistent`: pro yes, flash no
- q051 `consistent`: pro yes, flash no
- q055 `consistent`: pro yes, flash no
- q074 `consistent`: pro yes, flash no
- q118 `consistent`: pro yes, flash no
- q125 `consistent`: pro yes, flash no

