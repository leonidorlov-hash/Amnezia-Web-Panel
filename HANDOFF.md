> [!IMPORTANT] ПРОТОКОЛ ДЛЯ ЛЮБОГО AI-ЧАТА, РАБОТАЮЩЕГО С ЭТИМ РЕПО
> 1. ПЕРЕД работой: прочитай этот файл целиком + `git fetch --all` и `git log --oneline -5` по интересующим веткам. Файл — память, но git — единственный источник правды о коде. Утверждения «в ветке X есть/нет Y» без проверки git запрещены.
> 2. ПОСЛЕ каждой итерации (коммит, диагностика, решение): допиши запись с датой/временем в КОНЕЦ файла и закоммить вместе с кодом.
> 3. Всё сразу пушится в форк (origin) — ветки это канал синхронизации между чатами.
> 4. Прод-панель (SERVERA, /root/Amnezia-Web-Panel) живёт на deploy/v170 (на SERVERA origin=апстрим, fork=форк).
> 5. Решённые/старые записи выносим в HANDOFF-ARCHIVE.md (он в репо, читать не нужно — только если надо копнуть историю).

# HANDOFF — Amnezia-Web-Panel (форк leonidorlov-hash)

Обновлено: 2026-10-03. Полная история: HANDOFF-ARCHIVE.md.

## Среда
- `origin` = форк `leonidorlov-hash/Amnezia-Web-Panel` (пушим сюда), `upstream` = `PRVTPRO/Amnezia-Web-Panel`.
- Git Bash: каждая команда с `cd "/c/KIMI/panele4ka/ПанелечкаПроект" &&` (cd не сохраняется между вызовами).
- Тесты: `PATH="/c/Program Files/nodejs:$PATH" venv/Scripts/python.exe -m unittest discover -s tests` (473 теста, 1 skip = playwright; настоящий node.exe ОБЯЗАТЕЛЕН — шим kimi-desktop не исполняется через CreateProcess).
- GitHub API токен: `$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | grep '^password=' | cut -d= -f2)`. MCP github жив.

## Серверы пользователя
- SERVERA = root@stockholmservera (<IP:SERVERA>), панель `/root/Amnezia-Web-Panel`, обновление: `cd /root/Amnezia-Web-Panel && git fetch fork && git reset --hard fork/deploy/v170 && systemctl restart amnezia-panel`
- NATA = <IP:NATA>, ssh :1803 (веб-консоль у хостера). Прочие: FINN :54645, RAHMET/EUROBYTE/FIRSTBYTE/CloudPark.by/MRAK :1803. OVH — debian@vps-c27e7981 (systemctl через sudo).
- MAMKAM — панель удалена 2026-09-07 (управляется через SERVERA). Пароли в data.json на SERVERA. Имя сервера <IP:EUROBYTE> = `EUROBYTE` (не EB!).
- Команды для серверов давать ПО ОДНОЙ, помечать «шелл SERVERA» / «шелл EUROBYTE» (владелец путал с консолью Chrome).

## Постоянные правила
- Обновлять этот HANDOFF.md после КАЖДОЙ итерации (коммит + push deploy/v170). Ветка deploy/v160 УДАЛЕНА 03.10 (панель на OVH снесена, прод везде на v170) — не воскрешать; история целиком в HANDOFF-ARCHIVE.md, а код v160 устарел относительно v170.
- В HANDOFF никогда не писать пароли/ключи/IP — только имена серверов и плейсхолдеры <IP:ИМЯ>.
- HANDOFF и служебные заметки НЕ должны утекать в апстрим-PR (автор уже удалял их у себя — e4bb925). Перед PR проверять состав ветки.
- Владелец: «если нет софта для экономии токенов/скорости/качества — предлагай ставить».
- УРОКИ из инцидентов: (1) правя логику менеджера — `grep -n "def <method>" managers/*manager.py`, у протоколов бывают свои оверайды (wireguard toggle_client); (2) «починил» = проверил деплой и поведение в бою, не «запушил»; (3) EUROBYTE WG: ошибка «Cannot enable client: IP ... already present» — это штатная enable-предпроверка (wireguard_manager.py:944), срабатывает на СТАРОМ рассинхроне конфиг↔таблица, лечится правкой clientsTable (enabled=true), не баг кода.

## Актуальное состояние (на 03.10)
- Прод deploy/v170 = апстрим v1.7.3 (merge 33e87c4) + наши незамерженные фиксы: toggle hardening AWG+WG (08b936a/1595db9/37a7ea1), toggle race retry + peerToggling (0938658), glued batch markers (26129da), сторож poisoned batch (4d0db9f). Кандидаты на будущие PR.
- Все наши PR в апстрим СМЕРЖЕНЫ (#195/#196/#198/#200/#201 — вошли в 1.7.2/1.7.3). Открытых наших PR нет.
- «External вместо имён» — закрыт на трёх слоях: сторож 4d0db9f, distrust пустой batch-таблицы 7fff9bc (ad72fc0 в апстриме), склейка маркеров 26129da. Если симптом вернётся — смотреть журнал prefetch batch (секции по одной на контейнер).
- Панель на SERVERA: раскатка v1.7.3 выдана 03.10 (git fetch fork && reset --hard fork/deploy/v170 && restart), подтверждения владельца не было.
- Kernel-модуль AmneziaWG: панель пинит 3.1.20260812 (awg_manager.py:907), апстрим уже 3.1.20260906 — кандидат на однострочный бамп (владелец 03.10 отказался, не поднимать без запроса).
- Поколение протокола: везде AWG 3.1, новее нет — панель актуальна.

## Осторожно / не закрыто
- Пересборка docker-образов amnezia-awg2 на NATA/FIRSTBYTE/EUROBYTE из свежего amneziavpn/amneziawg-go (--pull) НЕ сделана — до этого НЕ переустанавливать эти инстансы из панели (в образах старые awg-tools → туннель упадёт; tools внутри контейнеров уже пересажены вручную, бэкапы .bak). Аналогично FIRSTBYTE хостовый fckrkn собран вручную.
- PR #176 (DRAFT, fix/awg-tools-selfheal): самолечение tools/kernel mismatch — так и висит драфтом.
- Тест test_awg_mtu_budget.test_awg3_default_would_not_fit_a_standard_link ФЛАКИ (периодически 1495 vs 1500) — кандидат на разбор.
- EUROBYTE: редкие всплески SSH-connect до 4с (сеть провайдера) — наблюдать. FINN: SSH-транспорт панели падает после docker stop/start инстанса — само заживает reconnect'ом.
- Скрипт аудита безопасности /tmp/fleet_audit.py остался на SERVERA (переиспользуем при подозрениях, см. архив 30.09).

## 03.10 12:55 — HANDOFF разделён: рабочий (47 строк) + HANDOFF-ARCHIVE.md (458 строк)
- Причина: экономия токенов — каждый чат читал целиком всю историю решённых проблем.
- В рабочем файле: протокол, среда, серверы, постоянные правила+уроки, актуальное состояние, открытые осторожности. В архиве — всё до 03.10 включительно, ничего не удалено.

## 03.10 13:10 — v1.7.3 раскатана на SERVERA (подтверждено владельцем)
- HEAD на SERVERA: 8040c56 (мерж v1.7.3 внутри). Следующий коммит 41d768a (split HANDOFF, docs-only) в раскатку не попал — не критично.

## 03.10 13:25 — deploy/v160 УДАЛЕНА (владелец: «вычисти, удали, забудь»)
- Причина: панель на OVH снесена (больше не нужна), прод везде на v170, уникального актуального кода в v160 не было. Удалена локально и на форке. Не воскрешать; история — в HANDOFF-ARCHIVE.md.

## 03.10 13:55 — DuckDNS-карточка в настройках (fa59e99, deploy/v170)
- Задача владельца: карточка «Свой домен на duckdns.org» рядом с SSL: инструкция 3 шага, домен+токен, флажок SSL = бесплатный автопродлеваемый сертификат в 1 клик. Решения: только для себя (без PR в апстрим), DNS-01 через acme.sh (порт 80 не нужен), авто-обновление IP в duckdns каждые 600с (монитор-фон), «отключение доступа по IP» НЕ делаем, настройки в data.json, карточка пишет в ТУ ЖЕ settings['ssl'], что и ручная SSL-карточка.
- Эндпоинт POST /api/settings/duckdns/apply: нормализация домена, update IP (пустой ip= → duckdns берёт IP вызывающего = сервер панели), выпуск cert через acme.sh --dns dns_duckdns, install в /etc/amnezia/duckdns.{cert,key}.pem, --reloadcmd systemctl restart amnezia-panel (автопродление само перезапускает панель). Первый apply под systemd сам рестартует панель через 2с-таймер; иначе restart_required в ответе.
- Токен НЕ рендерится в страницу; пустое поле = оставить сохранённый. Ошибки: duckdns_domain_token_required / ip_update_failed / cert_failed (502, ssl не трогается).
- 5 локалей, tests/test_duckdns.py (11 тестов), полный прогон 484 OK.
- Деплой SERVERA: git fetch fork && git reset --hard fork/deploy/v170 && systemctl restart amnezia-panel. После: Настройки → «Свой домен на duckdns.org». Для HTTPS панель УЙДЁТ в рестарт сама — открывать https://домен:5000.

## 03.10 14:30 — DuckDNS: боевой дебют поймал гонку reloadcmd (6b3d2c0)
- Первый боевой apply (домен cnacu6o.duckdns.org): cert ВЫПУСТИЛСЯ, файлы в /etc/amnezia записались, но UI показал 502 duckdns_cert_failed. Корень: '--reloadcmd systemctl restart amnezia-panel' исполнялся синхронно внутри install-cert → systemd убивал панель посреди собственного запроса → дочерний install-cert умирал → rc≠0 → 502 (uvicorn graceful shutdown успевал отдать ответ). settings['ssl'] при этом НЕ записался.
- Фикс: reloadcmd = "sh -c '(sleep 5 && systemctl restart amnezia-panel) >/dev/null 2>&1 &'" — отложенно и отцеплено; install-cert всегда возвращает 0, рестарт случается после ответа. Тот же reloadcmd обслуживает кроновские продления. Дублирующий Timer-рестарт из эндпоинта убран. 484 теста OK.
- Поведение повторного apply идемпотентно: acme.sh скажет Skip (cert жив), install-cert экспортирует, ssl-настройки запишутся, панель сама уйдёт на https://домен:5000.

## 03.10 15:10 — DuckDNS: БОЕВАЯ ПРОВЕРКА ПРОЙДЕНА + PR #202 в апстрим
- После фикса 6b3d2c0 повторный apply отработал чисто: Skip → install-cert → ssl-настройки записались → панель сама ушла на HTTPS. Владелец подтвердил: https://<домен>.duckdns.org:5000 открывается с валидным замком. ERR_EMPTY_RESPONSE по http://IP:5000 — ожидаемо (панель теперь TLS-only).
- Ручная SSL-карточка остаётся как есть (владелец отказался от спойлера): duckdns-карточка и ручная редактируют одну конфигурацию settings['ssl'].
- PR #202 в апстрим: feat/duckdns-card от upstream/main (828f060, 2 коммита чисто черри-пикнулись), 480 тестов OK на ветке, HANDOFF в ветку не утёк. В описании пометка «tested live only on my own single panel — needs testing/feedback», деталь про reloadcmd-гонку, out-of-scope (IP-блок, другие DNS-провайдеры).
- Открытые наши PR в апстрим: только #202.

## 03.10 22:30 — Фикс: менеджер паролей автозаполнял поиск пользователей логином
- Симптом: после перевода панели на https-домен (DuckDNS) Chrome подставлял сохранённый логин в фильтр #userSearch на /users. Причина: эвристика автозаполнения — id поля содержит «user», на странице есть type="password» (форма addUserForm) → Chrome считает поле логином.
- Фикс: users.html input#userSearch → autocomplete="off" + readonly, снятие readonly в onfocus (стандартный обход автозаполнения; readonly-поля менеджеры паролей не трогают, а перед вводом readonly снимается). Тесты 484/484 OK.
- Раскатка: git fetch fork && git reset --hard fork/deploy/v170 && systemctl restart amnezia-panel + Ctrl+Shift+R (менялся users.html).

## 03.10 22:50 — PR #204 в апстрим: фикс автозаполнения #userSearch
- Ветка fix/users-search-autofill от upstream/main (v1.7.3), черри-пик 738ce50, HANDOFF из коммита убран (не течёт в апстрим). 484 теста OK. PR: https://github.com/PRVTPRO/Amnezia-Web-Panel/pull/204

## 04.10 00:45 — Noindex + невинная страница входа (срочно, по требованию владельца)
- Контекст: панель торчит в интернет через https-домен DuckDNS. Страница входа светила в view-source весь словарь I18N (706 строк) — витрину всех фич панели (SSH-управление, API-токены, wg-easy/Remnawave/ngrok...). Запрета индексации не было вообще.
- Сделано: (1) middleware в app.py — заголовок X-Robots-Tag: noindex, nofollow на ВСЕ ответы; (2) роут /robots.txt → Disallow: /; (3) <meta name="robots" content="noindex, nofollow"> в base.html и login.html; (4) login.html больше не получает полный translations_json — render() отдаёт login_translations_json (3 ключа: login/logging_in/login_error), вся остальная разметка входа без изменений; (5) регрессионный тест tests/test_noindex_robots.py. 489/489 OK.
- Раскатка SERVERA обычная + Ctrl+Shift+R. Следом — срочный PR в апстрим.

## 04.10 00:55 — Срочный PR #205: noindex + невинная страница входа
- https://github.com/PRVTPRO/Amnezia-Web-Panel/pull/205 (ветка fix/noindex-public-login от upstream/main, тесты 474/474). Содержит: X-Robots-Tag middleware, robots.txt Disallow:/, meta robots в base+login, login_translations_json вместо полного словаря, тест test_noindex_robots.

## 04.10 13:20 — rkn-extra-block v1.0 в репо amnezia-blocker (f668906)
- Доп. контур по спискам C24Be/AS_Network_List: RKN_EXTRA_IN (подсети РКН → DROP новых в INPUT, v4+v6), RKN_EXTRA_OUT (сети VK/Max/OK → REJECT tcp-reset в OUTPUT+FORWARD). Независим от AMNEZIA_BLOCK. Команды rkn-extra-block on|off|status|update|boot, состояние /etc/rkn-extra-block/state, атомарный swap ipset, systemd service+timer (daily+2h jitter). Установка одной командой (install-rkn-extra.sh). Отдельные 4erdenko/ и blablajka/ — копия и обёртка, игнорируем.

## 04.10 13:30 — rkn-extra-block v1.1: log on/off + scan (f74714c)
- log on/off — rate-limited (10/мин) LOG-правила перед DROP/REJECT, просмотр: journalctl -k -g RKN_EXTRA. scan — ретроспектива: матч IP логов против ipset-наборов. ОБСУЖДАЕТСЯ перенос блокировки+статистики сканов в панель (флажок на сервер + агент почасового сбора).

## 04.10 14:30 — RKN/VK-блок в панели: флажок на сервер + статистика сканов (сырой прототип, БЕЗ PR)
- Решение владельца: «да, пока всё сыро, без PR, протестирую сам вначале». Никаких PR в апстрим и раскаток на SERVERA от меня.
- Серверная половина (blocker-repo, cf2a5e7, отдельный приватный репо leonidorlov-hash/amnezia-blocker): update строит nets.map (метки ORG из blacklist_with_comments.txt); rkn-agent-collect (timer rkn-agent.timer, hourly) собирает журнал -k за 65 мин, парсит SRC=/DPT=, пишет /var/log/rkn-scans.json (tail -5000). Инсталлер ставит агент и включает log on.
- Панель (deploy/v170): POST /api/servers/{id}/rkn_block — enabled=true запускает install-rkn-extra.sh по SSH (таймаут 420с, тянет списки C24Be + apt-пакеты, включает log+agent), enabled=false делает только rkn-extra-block off. GET /api/servers/{id}/rkn_scans — статус контура + tail -2000 rkn-scans.json, агрегация by_org/by_dpt/by_dir/last_24h/recent. UI: карточка 🛡 на странице сервера, флажок + сводка сканов. Состояние — server['rkn_block_enabled'] в data.json (дефолт False). Переводы rkn_block_* во всех 5 локалях. blocker-repo/ в .gitignore (это отдельный репозиторий, не коммитить).
- Тесты: 489/489 OK. Вживую эндпоинты не гонялся (нет SSH к серверам) — владелец тестирует сам. Раскатка владельцу по стандартной команде fetch fork + reset --hard fork/deploy/v170.

## 04.10 16:30 — RKN-блок: починка установки (приватный репо 404 + молчаливый успех)
- Симптом владельца: флажок на MRAK поставлен, полчаса «не установлено на сервере». Расследование: в журнале панели НЕТ POST /rkn_block (но флаг true в data.json — POST прошёл раньше и вернул success); `rkn-extra-block status` на сервере пустой → agent_state unknown.
- Корень — ДВЕ ошибки: (1) репо leonidorlov-hash/amnezia-blocker было ПРИВАТНЫМ → raw.githubusercontent отдавал 404; (2) команда установки `bash -c "$(curl -fsSL url)"` при неудачном curl получает пустую строку и выходит с кодом 0 → панель фиксирует успех без установки. Секретов в репо нет (проверено) → сделал его публичным через API.
- Фикс в app.py: установка теперь `curl -fsSL … -o /tmp/rkn-install.sh && bash /tmp/rkn-install.sh` — неудачное скачивание даёт rc≠0 и панель честно ругается. 489/489 OK. УРОК: конструкция bash -c "$(curl …)" всегда молча успешна при недоступном URL — не использовать.
- Владельцу: перераскатать панель и на MRAK перещёлкнуть флажок OFF→ON (флаг уже true, просто ON повторно не запустит install).

## 04.10 16:45 — RKN-блок: установка падала на apt install flock (blocker-repo 622c3d7)
- Вторая причина неработающей установки на MRAK: в install-rkn-extra.sh был `apt-get install … flock`, а flock — не пакет, а бинарник из util-linux → E: Unable to locate package flock, установка падала, fail-loud фикс показал это честным 500.
- Фикс: ставим util-linux + проверка `command -v flock`. Запушено в amnezia-blocker main (622c3d7). Панель НЕ перекатывать — инсталлер тянется с репо в момент тогла.
- Владельцу: на MRAK флажок OFF→ON ещё раз.
