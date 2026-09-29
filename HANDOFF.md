> [!IMPORTANT] ПРОТОКОЛ ДЛЯ ЛЮБОГО AI-ЧАТА, РАБОТАЮЩЕГО С ЭТИМ РЕПО
> 1. ПЕРЕД работой: прочитай этот файл целиком и выполни `git fetch --all` + `git log --oneline -5` по интересующим веткам. Файл — память, но git — единственный источник правды о состоянии кода. Любое утверждение «в ветке X есть/нет Y» без проверки git запрещено.
> 2. ПОСЛЕ каждой итерации (коммит, диагностика, решение): допиши запись в конец файла с датой/временем и закоммить его вместе с кодом.
> 3. Всё, что сделано, немедленно пушится в форк (origin) — ветки это канал синхронизации между чатами.
> 4. Прод-панель (SERVERA, /root/Amnezia-Web-Panel) живёт на ветке deploy/v170 (с 28.09; ранее deploy/v160). Ремоты на сервере: origin=апстрим, fork=форк.

# HANDOFF — Amnezia-Web-Panel (форк leonidorlov-hash)

Обновлено: 2026-09-14 (ночь). Репо: `C:\KIMI\panele4ka\ПанелечкаПроект` (сам git-репо прямо в этой папке, venv в `./venv`).

## Среда
- `origin` = форк `leonidorlov-hash/Amnezia-Web-Panel` (пушим сюда), `upstream` = `PRVTPRO/Amnezia-Web-Panel`.
- Прод-ветка: `deploy/v170` (с 28.09; ранее deploy/v160) — панель на SERVERA и др. Ремоты на SERVERA: origin=апстрим, fork=форк.
- identity уже стоит локально в репо (user.name/email leonidorlov-hash).
- Тесты: `venv/Scripts/python.exe -m unittest discover -s tests` (277 тестов на deploy, 1 skip = playwright; на ветках от upstream/main ~271 — меньше, т.к. там нет части наших тестов).
- GitHub API токен: `$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | grep '^password=' | cut -d= -f2)`. MCP github тоже жив.
- Git Bash: `cd` не сохраняется между Bash-вызовами — каждая команда начинается с `cd "/c/KIMI/panele4ka/ПанелечкаПроект" &&`.

## Открытые PR в апстриме (11 шт., на 2026-09-14)
- #163 fix(ssh): sudo-пароль через stdin — `fix/sudo-password-stdin`
- #165 feat(awg): IPv6 DNS (DNS6) — `feat/dns6`
- #166 feat(users): отвязка ✂️ + диплинки — `feat/unlink-deeplink` (var currentConnsUserId!)
- #167 feat(users): linking UX (мультивыбор, no-reload, анти-дубль) — `feat/link-ux` (var там же!)
- #168 fix(users): get_clients через _manager_call + ключи i18n — `fix/clients-and-i18n`
- #169 feat(users): богатые карточки + лампочка юзера — `feat/users-rich-cards` (стек на #166)
- #170 feat(server): привязка из редактора пира + мелочи — `feat/peer-editor-link` (стек на #169)
- #172 fix(ui): полл vs редактор, лампочка без полного релоада, тосты — `fix/conn-list-ux`. Обновлён 13.09 поздно: + silent refresh после сохранения пира (черри-пик 0b20cfc, коммит 9dfcf48)
- #173 fix(wireguard): краш get_client_config при привязке WG-пира (EN) — `fix/wg-get-client-config`
- #174 fix(ssh): dead server не морожит панель — event loop (66 эндпоинтов в to_thread) + circuit breaker + keepalive 15s + настраиваемый cooldown — `fix/ssh-eventloop-upstream` (4 чистых коммита от upstream/main; WG-часть отсюда убрана, она в #173)
- #175 fix(awg): апгрейд устаревшего kernel-модуля вместо пропуска — `fix/awg-kmod-upgrade` (один hunk в setup_kernel_module)

Порядок мержа стека: #166 → #169 → #170. Остальные независимы.
ВАЖНО: в #166 и #167 объявления `var currentConnsUserId/Username` (не let) — иначе дубль `let` после мержа обоих = SyntaxError. Не менять обратно!

## Уже смержено автором
Все 32 прошлых PR (#68…#152), включая #150 (лампочки/черепаха/спиннеры), #151 (vendor CDN), #152 (роли), #141 (IPAM), #134 (импорт wg-easy).

## deploy/v160 поверх апстрима (14.09)
Всё рабочее из deploy отправлено в PR (раскладка выше). Последние коммиты deploy:
- `ee780a7` — WG get_client_config фикс + keepalive 15s (→ #173 и #174)
- `b869f15` — настраиваемый ssh_cooldown_base (→ #174)
- `0b20cfc` — silent refresh после привязки/отвязки (→ #172)
- `d8b8240` — апгрейд устаревшего kernel-модуля (→ #175)
- HANDOFF.md коммитится в репо (протокол синхронизации чатов — в шапке файла).

## Kernel-модуль AmneziaWG 3.1.20260812 (14.09, закрыто)
- Установлен/обновлён вручную через DKMS на NATA (1.0.20260611→3.1), EUROBYTE (→3.1), FIRSTBYTE (1.0.20251009→3.1). Контейнеры перезапущены, старые версии dkms-remove'нуты.
- SERVERA и ранее был на 3.1. Userspace amneziawg-go не трогать — fallback внутри контейнера.
- Корневая причина в панели (skip при любой версии) исправлена → PR #175.
- Замечено: на FINN SSH-транспорт панели падает после каждого docker stop/start (conntrack/NAT сброс при перепрограммировании iptables докером) — само заживает reconnect'ом, решили оставить как есть.

## Инцидент «нет инета после апгрейда модуля» (14.09, закрыто)
- Причина: новый kernel-модуль 3.1 + старые awg-tools (v1.0.20210914) в 5-месячных docker-образах → `awg setconf` EINVAL, туннель не поднимался. Пары «модуль↔tools» должны совпадать.
- Починено пересадкой свежих tools (awg + awg-quick из контейнера SERVERA, v3.1.20260812) в контейнеры: NATA amnezia-awg2, FIRSTBYTE amnezia-awg2, EUROBYTE amnezia-awg2. Бэкапы старых: /opt/amnezia/awg/awg.bak и awg-quick.bak внутри контейнеров (на хосте в примонтированной папке).
- FIRSTBYTE дополнительно: хостовый инстанс fckrkn (awg-quick@awg0, /etc/amnezia/amneziawg) — собраны amneziawg-tools v3.1.20260812 из исходников (github amnezia-vpn/amneziawg-tools, make install), бэкапы /usr/bin/*.bak. Сервис active, handshake'и пошли. Переживает ребут.
- Docker-заплатка переживает restart/ребут хоста, НО не пересоздание контейнера из старого образа.
- НЕ СДЕЛАНО (важно!): пересборка docker-образов amnezia-awg2 на NATA/FIRSTBYTE/EUROBYTE из свежего amneziavpn/amneziawg-go (--pull). До этого момента нельзя переустанавливать эти инстансы из панели — вернётся старые tools и туннель упадёт.
- Остальные серверы (FINN, RAHMET, MAMKAM, MRAK, CloudPark) модуль не обновляли — у них согласованные старые пары, всё работает.

## Расследование «медленных серверов» (13.09, закрыто)
- Причина подвисаний с NATA: iptables-лимит `DROP tcp dpt:1803 ctstate NEW limit: above 3/min` на самом NATA. Панель при переподключениях упиралась в лимит. Лечение: на NATA добавлено `iptables -I INPUT 3 -p tcp -s <IP:SERVERA> --dport 1803 -m conntrack --ctstate NEW -j ACCEPT` + `netfilter-persistent save`. После — 6/6 OK.
- Остальные 8 серверов проверены (iptables + legacy + conntrack) — лимитов нет. EB имеет редкие всплески до 4с (сеть провайдера, не фаервол).
- Из панели серверы опрашиваются по ssh: SERVERA локален; у остальных порт из data.json `ssh_port` (не путать: `s.get('port',22)` в ad-hoc скриптах — дефолт, а не реальность).

## Серверы пользователя
- SERVERA = root@stockholmservera (<IP:SERVERA>), панель `/root/Amnezia-Web-Panel`, обновление: `cd /root/Amnezia-Web-Panel && git fetch fork && git reset --hard fork/deploy/v170 && systemctl restart amnezia-panel` (на SERVERA origin=апстрим, fork=форк)
- OVH = debian@vps-c27e7981, `/home/debian/Amnezia-Web-Panel`, systemctl через sudo
- NATA = <IP:NATA>, ssh :1803 (веб-консоль у хостера есть)
- MAMKAM — панель удалена 2026-09-07 (управляется через SERVERA)
- Прочие: FINN :54645, RAHMET/EUROBYTE/FIRSTBYTE/CloudPark.by/MRAK :1803. Пароли в data.json на SERVERA. Имя сервера <IP:EUROBYTE> = `EUROBYTE` (не EB!).

## Незакрытые вопросы
- Keepalive 15s — пользователь тестирует на живой панели (на момент записи).
- Автообновление панелей до новых релизов автора — по запросу пользователя.
- EUROBYTE (<IP:EUROBYTE>): редкие всплески SSH-connect до 4с (сеть провайдера, не фаервол) — просто наблюдать.

## ПРАВИЛО (установлено 14.09): обновлять этот HANDOFF.md после КАЖДОЙ итерации/действия — инциденты, диагнозы, фиксы, статусы. Не откладывать.

## Инцидент «docker build падает на EUROBYTE из панели» (14.09, в работе)
- Симптом: установка инстанса AWG 3.1 на EUROBYTE падает на «Сборка контейнера», ошибка выглядит обрывком лога pull слоёв amneziawg-go.
- Диагноз: диск/реестр/сеть в норме (df 46%, реестр 0.4с, `docker pull amneziavpn/amneziawg-go:latest` = 1.9с). Ручная сборка `docker build --no-cache --pull -t amnezia-awg3 /opt/amnezia/amnezia-awg3` на EUROBYTE прошла успешно. Причина падения из панели: жёсткий таймаут SSH-команды 300с убивал сборку посреди pull; обрезанный stderr выглядел как «битый лог».
- Фикс в deploy: `eac5b31` — таймаут сборки 900с + честное сообщение об ошибке при пустом stderr. В апстрим пока НЕ отправлен (следующая партия).
- Побочное требование пользователя: панель не должна обрезать/терять логи ошибок при работе с инстансом — учтено в eac5b31 (полный stderr в сообщении).
- СТАТУС: жду от пользователя повторную установку AWG 3.1 на EUROBYTE из панели после `git pull` на SERVERA. Кэш docker на EUROBYTE тёплый — должно пройти быстро. Если упадёт — просить новый текст ошибки.

## PR #176 (DRAFT): самолечение tools/kernel mismatch
- `2255002` (deploy) → ветка `fix/awg-tools-selfheal` от upstream/main.
- Что делает: start.sh контейнера при старте сравнивает версию awg-tools с версией kernel-модуля; при mismatch пересобирает tools v3.1 из исходников внутри контейнера. Плюс при установке инстанса предупреждение, если sibling-инстансы на старых tools.
- Описание PR ru+en, пометка: kernel 3.1 = высокая скорость без нагрузки на CPU (предпочтительнее userspace), просьба протестировать. DRAFT по просьбе пользователя.

## Текущий статус deploy/v160 (14.09, ~13:20)
- HEAD: `eac5b31` (build timeout 900s). Панель на SERVERA: git pull выдан, вывод не видел — при следующем контакте проверить `git -C /root/Amnezia-Web-Panel log --oneline -1`.
- Открытые PR: 12 шт. (#163,#165,#166,#167,#168,#169,#170,#172,#173,#174,#175,#176-draft). CI-статусы не проверял — предложить.

## Ближайшие отложенные задачи
- Пересборка образов amnezia-awg2 на NATA/FIRSTBYTE/EUROBYTE из свежего amneziavpn/amneziawg-go (--pull) — до этого НЕ переустанавливать эти инстансы из панели.
- После подтверждения установки AWG3 на EUROBYTE: проверить `docker exec amnezia-awg3 awg show` и версию tools, зафиксировать тут.
- Отправить build-timeout фикс (eac5b31) в апстрим следующей партией.

## 14.09 ~13:40 — итерация по инциденту docker build EUROBYTE
- Панель на SERVERA подтверждена на eac5b31, но ошибка всё равно приходила обрезанной, а ручной `docker build --no-cache --pull` той же командой — EXIT=0 (дважды). Значит: (а) обрезка не в бэкенде (app.py отдаёт str(e) целиком), (б) падение специфично для SSH-сессии панели.
- Фикс `4603a84` (deploy): сборка пишет лог в /tmp/docker-build-<name>.log на сервере, через канал возвращается только tail -c 6000 (убирает флуд BuildKit-прогресса через SSH-канал — вероятная причина смерти сборки на флаки-линке EUROBYTE, и гарантирует полный текст ошибки). Фронт: clearInterval в catch (строки прогресса больше не печатаются после ошибки) + рендер ошибки через textContent (innerHTML мог глотать хвост сообщения).
- Заметка: ремоут форка называется `origin` (не fork!). Пуш: `git push origin deploy/v160`.
- СТАТУС: жду от пользователя `git pull` на SERVERA + повторную установку AWG 3.1 на EUROBYTE.

## 14.09 ~14:10 — разгадка «docker build падает на EUROBYTE» (закрыто)
- Журнал показал: канал SSH закрывается через ~2с после старта сборки (code -1, пустой вывод), а docker-демон дособирал образ до конца (image 61cefcb838 существует, лог полный). Ложная ошибка панели. Отвечающий за закрытие канала — флаки-линк EUROBYTE (точную причину смерти транспорта не доказали; disconnect() для пуловых менеджеров уже no-op, не он).
- Фикс `0401a36` (deploy): сборка запускается отсоединённо (nohup, код выхода в файл), панель опрашивает code-файл свежими короткими каналами каждые 5с до 900с. Смерть канала/транспорта больше не фальсифицирует результат. Ошибка сборки возвращает tail лога; лог остаётся на сервере /tmp/docker-build-<name>.log.
- Побочка замечена: спам в журнале "container 26ec2549... is not running" — это UI поллит упавший контейнер (какой-то инстанс на каком-то сервере мёртв). Отдельный вопрос, не трогали.
- СТАТУС: жду git pull на SERVERA + повторную установку AWG 3.1 на EUROBYTE. Образ уже собран — установка должна пройти до конца (сборка закэшируется/пропустится быстро? нет, --no-cache пересоберёт ~3мин, это нормально).

## 14.09 14:25 — EUROBYTE AWG 3.1 установлен (инцидент закрыт)
- Установка из панели прошла полностью (detached-сборка 0401a36 работает). Туннель поднят: awg0, pubkey /m666swwKRvL..., tools v3.1.20260812 в новом образе — mismatch больше не грозит.
- СТАТУС: инцидент docker build EUROBYTE ЗАКРЫТ. Фиксы eac5b31+4603a84+0401a36 кандидаты в апстрим следующей партией.

## 14.09 — фича: настраиваемый живой поллинг пиров (в работе)
- Запрос пользователя: в managementModal настройка интервала живого обновления списка пиров. Дефолт 0 = ВЫКЛ (раньше было захардкожено 5с, наш же PR). Шаги: 0,5,10,15,20,45,120,300,600.
- Реализация: поле server['peer_poll_interval'], эндпоинт POST /api/servers/{id}/peer_poll_interval, селект в managementModal, loadConnections использует PEER_POLL_INTERVAL.

## 14.09 14:35 — фича поллинга пиров ГОТОВА (2f8584f, deploy)
- Эндпоинт POST /api/servers/{id}/peer_poll_interval (валидация по шагам 0,5,10,15,20,45,120,300,600), поле server['peer_poll_interval'], дефолт 0 = выкл.
- UI: селект в managementModal под ssh cooldown (ключи peer_poll_* в 5 локалях). loadConnections: оба места с 5000мс заменены на PEER_POLL_INTERVAL, планируется только при >0.
- ВАЖНО: после выката на SERVERA живое обновление у всех серверов ВЫКЛЮЧИТСЯ (дефолт 0) — это по запросу пользователя. Включать вручную per-server.
- Кандидат в апстрим следующей партией (вместе с build-фиксами eac5b31/4603a84/0401a36).

## 14.09 14:45 — PR #177 отправлен в апстрим
- Ветка feat/peer-poll-interval от upstream/main (черри-пик 2f8584f → edd6f2f; конфликты только в translations, решены ours + повторное добавление ключей). 285 тестов OK.
- PR #177: https://github.com/PRVTPRO/Amnezia-Web-Panel/pull/177 (EN-описание, пометка про behavior change: поллинг выключится по дефолту).
- MCP create_pull_request вернул "fetch failed", но PR реально создался — при повторе API ответил "already exists". Проверять факт создания перед ретраем.
- Открытые PR теперь 13 шт. (#163,#165,#166,#167,#168,#169,#170,#172,#173,#174,#175,#176-draft,#177).

## amnezia-blocker (записано 14.09; про скрипт ранее не знал)
- Пользовательский скрипт `/etc/amnezia-blocker/blocker.sh` v3.2 (IPv4+IPv6+TCP RST+flock+параллельный DNS+прогресс). Резолвит домены из https://mamkam.spb.ru/domains.txt (кэш /var/cache/amnezia-blocker/domains.conf) в ipset'ы `amnezia_blocked4`/`amnezia_blocked6` (maxelem 100000, заливка через ipset restore, атомарный swap temp→main; при нулевом резолве старый список сохраняется).
- Блокировка: цепь AMNEZIA_BLOCK (REJECT tcp-reset для TCP dst+src, REJECT для остального), прыжки в FORWARD и OUTPUT на позицию 1 (iptables и ip6tables при поддержке inet6).
- Команды: on|off|status|update|reload|check. Состояние в /etc/amnezia-blocker/state, лог /var/log/amnezia-blocker.log, лок /run/amnezia-blocker.lock. Зависимости: ipset, dnsutils, iptables (доставляет apt сам).
- Замечено ранее: на NATA в iptables уже видели REJECT'ы `match-set amnezia_blocked4` — значит там blocker стоит и работает.
- ЗАДАЧА (в работе): проверить почему не работает на EUROBYTE + пакетная проверка всех серверов.

## 14.09 15:00 — PR #178 отправлен в апстрим
- Ветка fix/awg-build-detached от upstream/main: черри-пики eac5b31→0c5c344, 4603a84→fd96aca, 0401a36→8417581, все чисто, 285 тестов OK.
- PR #178: https://github.com/PRVTPRO/Amnezia-Web-Panel/pull/178 (EN: три причины падений сборки, три коммита, тест на проде).
- Открытые PR: 14 шт. (+#177, #178).

## 14.09 16:05 — диагностика blocker EUROBYTE (закрыто: blocker РАБОТАЕТ)
- state=on, ipset 716 IPv4, цепь AMNEZIA_BLOCK в FORWARD позиция 3, cron каждые 6ч + @reboot, резолв свежий (14.09 12:17, 1038 IPv4). web.max.ru резолвится в 155.212.204.{78,143,193} — ВСЕ в ipset. Т.е. со стороны сервера блокировка корректна. Если сайт у пользователя открылся — трафик шёл не через EUROBYTE, либо клиент не в туннеле, либо DoH у клиента → другие IP. Отложено.

## 20.09 19:45 — ИНЦИДЕНТ: создание пира/инстанса AWG3.1 на RAHMET удалило боевой инстанс с пирами
- Симптом: в момент создания нового инстанса AWG 3.1 на RAHMET удалился существующий боевой инстанс со всеми пирами. На MINSK не воспроизводится. Гипотеза №1: check_protocol_installed/remove_container в install_protocol сносит старый контейнер при коллизии имени (например container_name совпал у нового и старого инстанса из-за рассинхрона data.json и реальности). ЗАДАЧА: найти баг, понять почему MINSK чист, проверить все сервера и инстансы.

## 20.09 — ИНЦИДЕНТ RAHMET: разбор закрыт, фикс c544cc3
- Механика: 19.09 20:28 (journal) панель пошла по пути ПЕРЕУСТАНОВКИ awg3 (install_another=false): шаг «Remove old container» сделал docker rm -fv amnezia-awg3 с боевыми пирами. У AWG-контейнеров НЕТ bind-mount /opt/amnezia/awg — состояние внутри контейнера, пиры стёрты безвозвратно. Контейнер пересоздан 19.09 23:39 (+05). Пользователь пересоздал пиров вручную (rahmet31...).
- Триггер: UI маркетплейса при недетекте статуса инстанса (флаки SSH) показывает «Установить» вместо «Установить ещё один» → plain install → reinstall-путь. На MINSK статус определился → была кнопка «Install another» → amnezia-awg3-2 → баг не воспроизвёлся.
- Пакетная проверка всех 8 серверов (data.json ↔ docker ps -a): рассинхрона НИГДЕ нет. Лишние неуправляемые контейнеры: amnezia-wg-easy на FINN/RAHMET/FIRSTBYTE/MRAK (ок).
- Фикс c544cc3 (deploy): _backup_container_state — docker cp /opt/amnezia/awg → /opt/amnezia/backups/<container>-<ts> перед удалением; сбой бэкапа = warning в логе установки, установку не блокирует. 278 тестов OK.
- RAHMET сменил IP: <IP:RAHMET-старый> → <IP:RAHMET> (порт 1803). data.json на SERVERA надо обновить (host). НЕ связано с багом.
- ОТЛОЖЕНО: (1) bind-mount /opt/amnezia/awg для новых инстансов — настоящая долговечность; (2) авто-restore пиров после переустановки; (3) фикс c544cc3 → апстрим; (4) обновить host RAHMET в data.json.

## 20.09 ~21:40 — Оптимизация /check (коммит 8fea402, deploy/v160)
- Проблема: /check открывал страницу сервера по ~19-31 SSH-команде (per-container docker ps/inspect + per-container cat конфигов) → долгое ожидание.
- Решение: (1) ssh_manager.docker_ps_snapshot() — один 'docker ps -a' с TTL 10с, docker_container_state() отвечает из снапшота; (2) AWGManager.prefetch_awg_state() — ОДНА ssh-команда тянет awg0.conf + clientsTable всех запущенных AWG-контейнеров (TTL 15с), check/status читают из батча.
- Инвалидация: docker ps — после install/remove/toggle контейнера; батч — в _invalidate_config_cache и _save_clients_table (закрыт риск потерянного обновления clientsTable).
- Fallback: все менеджеры при отсутствии новых методов (старые фейки/моки) идут старым путём. DNS-менеджер не тронут сознательно.
- Эффект: /check RAHMET ~19 команд → ~4, FINN ~31 → ~6. 283 теста OK (+5 новых в tests/test_status_batch.py).
- ОТЛОЖЕНО (не батчено): telemt docker inspect/port, extras adguard/nginx, DNS — малая доля команд.

## 20.09 ~22:00 — PR #185 в апстрим + ревью чужих PR
- PR #185 (fix/backup-and-check-batching): cherry-pick c544cc3+8fea402 на чистый upstream/main, 290 тестов OK. Бэкап пиров перед reinstall + батчинг /check.
- Ревью PR #177/#178 (наши) и #179-#183 (Almeonamy): все open, mergeable=clean, нашей вины нет — базируются на том же main 02c1182, наши PR их не ломали.
- Потенциальные пересечения ПОСЛЕ мержа (следить): #179 и #185 оба трогают awg_manager.py/app.py; #183 и #178 оба трогают install_protocol в awg_manager.py (разные хунки — mtu ~1044 vs build ~1084, должны смержиться); #177 и #179 оба трогают server.html.
- Поставлены +1 и комментарий поддержки на PR #183 (авто-MTU) от leonidorlov-hash: подтверждена проблема на наших 8 серверах, предложено тестирование на флоте.

## 21.09 ~00:40 — Флажок server stats (коммит d8badbb, deploy/v160)
- История: a86e4f9 (09.09) добавил чекбокс в managementModal, 97ab9e2 его откатил. Теперь возвращён с дефолтом ВЫКЛ: снят = loadServerStats() выходит ДО запроса, ноль обращений к /stats, секция скрыта. Хранение localStorage (per-browser). Ключ server_stats_toggle во всех 5 локалях. 283 теста OK.
- Открыто: баг FINN awg3 «Подключения: 0» — на сервере 11 пиров и clientsTable целый (4506 байт), врёт панель. Жду вывод git log + journalctl от пользователя.

## 21.09 ~00:50 — Баг «Подключения: 0» на FINN awg3 (коммит e2e80c5)
- Симптом: карточка awg3 на FINN писала 0 подключений при 11 пирах (conf+clientsTable целы, 4506 байт).
- Причина: _get_clients_table молча возвращал [] на JSONDecodeError. Усечённый JSON (флаки SSH, разрыв канала посреди чтения; в логе 23:33:01 был 'NoneType open_session' на FINN) выдавал ложный 0. Поведение было и до батчинга, но батч-префетч (8fea402) делал одно флаки-чтение общим для всех инстансов.
- Фикс: битый clientsTable из префетча → запись выкидывается, прямое перечитывание; битое прямое чтение → RuntimeError → get_server_status отдаёт error, UI не показывает число вместо лживого 0. +2 регрессионных теста. 285 тестов OK.
- Замечено попутно (не чинил): 'NoneType open_session' = гонка shared SSH-транспорта (transport=None в exec_command); ретрай не спас, но через 5с команды пошли. Кандидат на отдельный фикс (перепроверка transport после reconnect / сериализация force_disconnect).

## 21.09 ~01:00 — Гонка SSH-транспорта (коммит 47ec251, deploy/v160)
- Корень 'NoneType open_session': force_disconnect (eviction пула, app.py:322) брал только _conn_lock, exec — только _exec_lock → eviction обнулял self.client между ensure_connected и exec_command; retry проигрывал ту же гонку повторно.
- Фикс: _conn_lock стал RLock и держится на всю команду/SFTP-операцию (run_command, upload/download/file_exists); eviction ждёт завершения in-flight команды. Fallback _conn_lock_of() для тестовых объектов без __init__.
- Регрессионный тест tests/test_ssh_transport_race.py: фейковый exec блокируется, eviction обязан ждать; 286 тестов OK.
- Панель на SERVERA: обновить (git pull --ff-only && systemctl restart amnezia-panel) — покрывает d8badbb (stats-флажок) + e2e80c5 (ложный 0) + 47ec251 (гонка).
- PR #185 усилен: cherry-pick e2e80c5+47ec251 в fix/backup-and-check-batching (54fd02b, 2b3462c), 293 теста OK, описание обновлено (4 части: бэкап, батчинг, ложный 0, гонка SSH).

## 22.09 — БАГ (отложен): юзер с ролью user видит /my и пиров при глобально выключенном self-service + редирект-петля 403
- Симптом: self-service выключен глобально (settings.enabled=false), но юзер с ролью 'user' спокойно логинится и на /my видит своих пиров (список от /api/my/connections, который НЕ проверяет self-service — 403 кидает только /options).
- Плюс фронт-петля: apiCall (base.html:314) на ЛЮБОЙ 403/401 делает location.href='/login'; /login с живой сессией → 302 '/', '/' для user → 302 '/my' → /my дёргает /api/my/connections/options → SelfServiceError 403 → круг бесконечный (моргание страницы, спам 403 в консоли).
- Корень: (1) /my и /api/my/connections не проходят проверку self-service enabled; (2) domain-403 (SelfServiceError, connection_service.py _validate_channel/_get_eligible_user) неотличим от auth-403 на фронте.
- ПЛАН ФИКСА (не делать до команды): (а) гейт: при глобально выключенном self-service юзерам роли 'user' запрещать вход (login: проверять settings.enabled, отдавать осмысленную ошибку) или редиректить с /my на страницу-заглушку; /api/my/* тоже проверять; (б) фронт: редирект на /login только по 401, 403 показывать тостом с текстом из тела ответа (правка base.html apiCall + catch в my_connections.html loadSelfServiceOptions). Не забыть про /api/my/connections — сейчас он 200 при выключенном self-service, список пиров утекает.
- Заметка: admin/support /my не показывается вообще (их '/' = index), проблема только роли 'user'.

## 22.09 ~21:40 — Инцидент «External вместо имён» (коммит 7da1bc5)
- Диагноз: чужой советчик описал механику верно (External = пир из conf, не найденный в clientsTable), но причина оказалась другой: amnezia-awg2 на FINN был ШТАТНО остановлен пользователем (Exited 143, 2 дня); панель каждый опрос долбила docker exec в стопнутый контейнер → code 1 → тихий [] → при флаке conf+table читались неодновременно → External. На NATA всё цело (контейнер Up 8 дней, ключи conf↔table совпали 11/11).
- Фикс: _get_clients_table сначала смотрит docker-снапшот: стопнут → [] без exec (нет спама лога); жив + файл есть + cat упал → RuntimeError; жив + файла нет → [] (свежий инстанс). +3 теста, фейк test_awg_config_cache научил test -f. 289 тестов OK.
- Урок: Exited(143) ≠ падение — уточнять у пользователя, штатно ли остановлен.
- Счётчик «Подключения» занижал: считал только clientsTable, External-пиры (в conf, не в таблице) не входили. Фикс: clients_count = |table ∪ conf|, external_count отдельно; то же в wireguard_manager. +1 тест, 290 OK.
- Коммит fee619c («connections count includes conf-only peers») запушен в deploy/v160. Панель на SERVERA: требуется git pull --ff-only && systemctl restart amnezia-panel (поверх 47ec251 — покрывает 7da1bc5 + fee619c). Пользователь подтвердил: имена пиров на NATA вернулись; счётчик после фикса ещё не проверен.

## 22.09 ~21:55 — Текущее состояние (снапшот)
- deploy/v160 HEAD: fee619c. Локальные коммиты поверх апстрима: бэкап пиров, батчинг /check, stats-флажок, ложный 0, гонка SSH, стопнутый контейнер, счётчик с External. 290 тестов OK (skipped=1).
- PR #185 в апстрим: 4 коммита (11dda32, 39edc01, 54fd02b, 2b3462c), 293 теста. НЕ содержит 7da1bc5 и fee619c — предложено до-cherry-pick'нуть, ответа пользователя нет.
- Наши PR #177 (peer poll opt-in), #178 (detached build) — open, автор апстрима игнорирует. Чужие #179-#183 (Almeonamy) — open, clean; на #183 поставлены +1 и коммент.
- Отложенные хвосты: (1) bind-mount /opt/amnezia/awg + авто-restore после reinstall; (2) NATA IPv6 «No usable IPv6»; (3) amnezia-blocker EUROBYTE — технически работает, вопрос почему web.max.ru открылся (возможно проверка не через VPN); (4) баг self-service для роли user + редирект-петля 403 (план зафиксирован выше, ждёт команды).

## 22.09 ~22:40 — «External на NATA» закрыт: это был устаревший рендер, не баг данных
- Симптом: на странице NATA список awg2 показывал 6 свежих имён (созданы 14–20.09) + ~69 External с дублями IP, счётчик «75». External шли сразу после выключенного пира.
- Проверки (все чисто): на NATA контейнер amnezia-awg2 Up 8 дней; clientsTable 29423 байта, 69 записей, все 69 ключей из awg0.conf в таблице (MISSING=0); прямое чтение через SSHManager — 69/69; реальный get_clients('awg2') — 69/69 с именами, 0 external, 0 выключенных.
- Причина: страница была открыта раньше и список загрузился в момент частичного чтения clientsTable (6 записей доехали, остальные — нет → conf-пиры дорисовались как External). Пир-поллинг по умолчанию ВЫКЛ (фича PR #177), поэтому старый рендер не перезагружался сам. Три клика по «Подключения» (selectProtocolForConns) форсировали перезагрузку — имена вернулись.
- Панель на SERVERA на fee619c (подтверждено). Спам «code 1» в логе — exec в отсутствующие/стопнутые контейнеры (servera/RAHMET/CloudPark/MAMKAM/MRAK без awg2, FINN awg2 штатно остановлен) — безвреден, но кандидат на тишину в логе.
- Урок: при жалобах на External/0 сначала сверять live-данные (get_clients) с экраном — расхождение = устаревший рендер. Идея на будущее: при ошибке загрузки списка показывать плейсхолдер «не удалось загрузить» вместо сохранения старого списка, либо авто-рефетч при возвращении вкладки в фокус.

## 28.09 15:50 — Инвентаризация панелей на флоте (перед удалением, фаза 1: проверка)
- Задача пользователя: оставить панель ТОЛЬКО на SERVERA, на OVH/NATA/FINN/FIRSTBYTE удалить «как будто не было». VPN-контейнеры/сервисы (amnezia-awg*, xray, blocker, routing, /opt/amnezia*) НЕ трогать — ими управляет SERVERA.
- Результаты проверки (dirs/systemd/proc/port5000/docker/cron):
  - MAMKAM: панели НЕТ (только /opt/amnezia контейнеры). Чисто.
  - RAHMET: панели НЕТ (только amnezia-blocker). Чисто.
  - EUROBYTE: панели НЕТ (только blocker). Чисто.
  - MRAK: панели НЕТ (amnezia-routing + blocker). Чисто.
  - FINN: панели НЕТ. Есть /root/amnezia-wg-easy-v2 + старый .ko.bak — НЕ панель, оставить.
  - FIRSTBYTE: ПАНЕЛЬ ЕСТЬ — /root/Amnezia-Web-Panel (venv), amnezia-panel.service enabled/active, pid 537 с 06.09, слушает 0.0.0.0:5000. Рядом /root/amnezia-manager.sh (содержимое НЕ проверено — проверить перед удалением), бэкапы *.tar.gz (не панель — оставить).
  - NATA: ПАНЕЛЬ ЕСТЬ — /root/Amnezia-Web-Panel, amnezia-panel.service («Amnezia Web Panel Service») active, pid 498, порт 5000. Рядом awg0-persistent.service FAILED — VPN-хостовый, НЕ панель, не трогать.
  - OVH: ПАНЕЛЬ ЕСТЬ — /home/debian/Amnezia-Web-Panel (venv), amnezia-panel.service active, pid 611299 с 04.09, порт 5000, systemd через sudo.
- Заметка: на NATA/FINN/EUROBYTE процессы /opt/amnezia/start.sh перезапущены сегодня ~14:35 — похоже на ребут хостов; на панели не сказалось.
- СТАТУС: план удаления для 3 серверов (FIRSTBYTE/NATA/OVH) показан пользователю, ждёт явного подтверждения.

## 28.09 16:50 — Удаление панелей на FIRSTBYTE/NATA/OVH ЗАВЕРШЕНО
- Подтверждено пользователем. На каждом: systemctl stop+disable amnezia-panel, удалён /etc/systemd/system/amnezia-panel.service, daemon-reload, rm -rf каталога панели (вместе с локальными data.json).
- Верификация на всех трёх: «Unit amnezia-panel.service could not be found», порт 5000 свободен, каталог удалён.
- FIRSTBYTE: /root/amnezia-manager.sh ОСТАВЛЕН — это отдельный bash-менеджер пиров хостового WG (/etc/amnezia/amneziawg/wg0.conf), не часть панели.
- НЕ тронуто везде: /opt/amnezia* (VPN-контейнеры/xray), amnezia-blocker, amnezia-routing (MRAK), cron, awg0-persistent.service на NATA (failed, VPN-хостовый), бэкапы *.tar.gz и исходники модуля, amnezia-wg-easy-v2 на FINN.
- ИТОГ: панель живёт только на SERVERA (/root/Amnezia-Web-Panel, fee619c). Управление OVH/NATA/FIRSTBYTE и остальными — удалённо с SERVERA через SSH (порты/пароли в data.json SERVERA).
- Побочка: локальные data.json удалённых панелей могли содержать записи, не перенесённые в SERVERA — пользователь в курсе, источник истины SERVERA.

## 28.09 19:50 — Фантомная карточка «Не установлен / Установить» после удаления инстанса (коммит b80a025, deploy/v160)
- Симптом: после удаления базового инстанса (напр. awg2) карточка AmneziaWG 2.0 оставалась в сетке установленных с бейджем «Не установлен» и кнопкой «Установить», если на сервере был ещё один инстанс семейства (awg2 #2).
- Причина: applyInstalledAppsVisibility решала видимость статической карточки через baseInstalled() (ЛЮБОЙ инстанс семейства установлен), а контент карточки рисует updateProtocolCard по конкретному базовому прото. Видимость семейная, контент инстансный → рассинхрон.
- Фикс: базовая карточка видна только когда установлен сам базовый инстанс (isAppInstalled(currentProtocolStatus[proto])). Доп. инстансы по-прежнему рисуются своими динамическими карточками (ensureProtocolCard). Маркетплейс без изменений (там семейная видимость корректна — «Установлено» + «Установить ещё один»).
- Бэкенд удаления НЕ тронут: /uninstall по-прежнему удаляет только свой контейнер и запись protocols[proto]; бэкап c544cc3 (инцидент RAHMET) intact.
- 290 тестов OK. Кандидат в апстрим следующей партией (вместе с 7da1bc5/fee619c).
- Панель на SERVERA: git pull --ff-only && systemctl restart amnezia-panel — покрывает b80a025.

## 28.09 21:40 — Порог conn-flood предупреждения 600 → 900 (коммит 7a1d660 deploy / 5b97881 upstream-ветка, PR #196)
- Проблема: CONN_WARN_THRESHOLD=600 (фича PR #100, в апстриме) давал ложные срабатывания на пирах без торрентов — Windows Delivery Optimization (P2P-обновления) держит ~500–800 соединений, пользователь наблюдал 600±50.
- Фикс: порог 900 (выше диапазона P2P-обновлений; реальные торренты 1000+). Комментарий в коде объясняет выбор.
- PR #196 в апстрим: https://github.com/PRVTPRO/Amnezia-Web-Panel/pull/196 (EN, ветка fix/conn-warn-threshold от upstream/main 8c9562b). Внимание: upstream/main ушёл вперёд — тестов там теперь 463 (не 271 как было в сентябре).
- deploy/v160: cherry-pick 7a1d660, 290 тестов OK, запушено.
- Панель на SERVERA: git pull --ff-only && systemctl restart amnezia-panel — покрывает 7a1d660.
- Открытые PR в апстриме теперь 15 шт. (+#196).
- Раскатка на SERVERA: выполняет сам пользователь 28.09 (команда: cd /root/Amnezia-Web-Panel && git pull --ff-only && systemctl restart amnezia-panel && git log --oneline -1; ожидается HEAD 7a1d660). Подхватывает b80a025 + 7a1d660.

## 28.09 21:45 — ОБНАРУЖЕНО: SERVERA сидит на deploy/v170, а не на deploy/v160 (вне этой сессии!)
- Репо на SERVERA: ветка deploy/v170 БЕЗ tracking — git pull падает. В HANDOFF про v170 ни слова — переход сделан в другой сессии/вручную, не задокументирован. Нарушение правила «писать в HANDOFF после каждого действия».
- Что такое origin/deploy/v170: upstream/main 1.7.0 (8c9562b, сегодня 18:27 у автора: «Security, Fixes and localization» + «Update server.html») + ТОЛЬКО 3 черри-пика: a9665cf (=7da1bc5 stopped-контейнеры), 8584763 (=fee619c счётчик External), dbc0050 (=b80a025 карточка). Создана ~19:51 28.09.
- Чего в v170 НЕТ из v160 (проверено git cherry-pick diff): SSH event loop + circuit breaker (#174), wg get_client_config (#173-часть), peer-poll (2f8584f), stats-флажок (d8badbb), silent refresh (0b20cfc), ssh cooldown (b869f15), ВСЯ линковка/юзеры (ade4196, 1c1e258, 2412b84, 3eb9675, 5f8355c...), vendor CDN (3c9c955), DNS6/sudo-stdin (#165/#163 — их коммиты в v160, в upstream не мержились), порог 900 (7a1d660). Автор 1.7.0 наши открытые PR почти не мержил — список уникальных патчей v160↔upstream почти совпадает со списком открытых PR.
- Риск: если панель реально работает на v170 — прод потерял почти все наши фиксы (в т.ч. антифриз панели на мёртвых серверах #174).
- Решение (согласовано дать пользователю): вернуть SERVERA на deploy/v160 (все фиксы, стабильно), отдельно собрать ПОЛНУЮ v170 = rebase остатка v160 на upstream 1.7.0 → тесты → только потом рассматривать переключение прода (там security-фиксы автора).
- Команда для пользователя на SERVERA: git checkout deploy/v160 && git branch --set-upstream-to=origin/deploy/v160 deploy/v160 && git pull --ff-only && git log --oneline -1 && systemctl restart amnezia-panel (ожидается HEAD 7a1d660).

## 28.09 ~20:15 — Проверка чужого коммита b80a025 (скрытие базовой карточки после удаления инстанса)
- Контекст: параллельная сессия сделала fix(ui): после удаления базового инстанса (напр. awg2) его статическая карточка оставалась в сетке как «Не установлен / Установить», если жил другой инстанс семейства (awg2__2) — видимость считалась по семейству (baseInstalled).
- Проверил дифф (только templates/server.html, +6/-1): visibility базовой карточки теперь = isAppInstalled(currentProtocolStatus[proto]) — это ровно installedProtocols[proto] из старой схемы, т.е. старое поведение минус «семейный» вклад. Логика /uninstall и бэкап c544cc3 не затронуты. Маркетплейс-статус (baseInstalled) не тронут — корректно.
- Краевые случаи ок: остановленный базовый инстанс виден (container_exists); до первого /check карточки скрыты — как и раньше; доп. инстансы рисуются своими динамическими карточками (ensureProtocolCard).
- Тесты: 290 OK (skipped=1). Вердикт: правка корректна, оставляем. Запушено в deploy/v160.
- ВАЖНО для обновления на v1.7.0: апстрим-релиз НЕ содержит 7da1bc5, fee619c, b80a025 — после перехода на v1.7.0 накатить их поверх (cherry-pick) или сначала отправить отдельным PR.

## 28.09 ~21:00 — Панель на SERVERA обновлена до v1.7.0 + наши 3 фикса
- Апстрим смержил всё 28.09: наши #177 (пир-поллинг opt-in), #178 (detached build), #185 (бэкап пиров + батчинг /check + гонка SSH + ложный 0); чужие #179, #180, #181, #183 (Almeonamy), #186 (Telemt), #188 (ещё фикс гонки SSH, rosticos), #192 (AWG3-детект в amnezia-awg2, Seraish) + security-пакет автора. Релиз v1.7.0 от 15:27 UTC.
- Бэкап перед обновлением: /root/Amnezia-Web-Panel.bak-20260928-1943.
- Переход: новая ветка deploy/v170 от тега v1.7.0 + cherry-pick наших трёх неслитых коммитов: 425bdd7 (7da1bc5, стопнутый контейнер), 872955e (fee619c, счётчик с External — был конфликт с header_protection из #192, разрешён: оставлены ОБА блока), ad05766 (b80a025, скрытие базовой карточки). Ремоты на SERVERA: origin = апстрим (!), fork = leonidorlov-hash, upstream = PRVTPRO (добавлен при обновлении).
- Тесты на сервере: 467 OK (skipped=4) — апстрим нагнал тестов. Панель: active, HTTP 200 на /login.
- Пользователю: жёсткое обновление страниц (Ctrl+Shift+R) — статика сменилась. Следить за счётчиком и списком NATA (наши фиксы на месте).
- Открыто: запушить deploy/v170 в форк (ветка пока только на SERVERA); собрать следующий PR в апстрим из 425bdd7+872955e+ad05766; старые отложенные хвосты (bind-mount, NATA IPv6, self-service баг, спам логов exec в несуществующие контейнеры).

## 28.09 ~21:20 — deploy/v170 запушена в форк, PR #195 в апстрим
- Ветка deploy/v170 (v1.7.0 + 3 коммита) собрана локально идентично серверной (те же cherry-pick, тот же конфликт в awg_manager разрешён так же: header_protection + счётчик оба оставлены), 467 тестов OK, запушена в origin (форк). Локальные SHA: a9665cf, 8584763, dbc0050 (на SERVERA: 425bdd7, 872955e, ad05766 — содержимое идентично).
- PR #195 в PRVTPRO/Amnezia-Web-Panel: "fix(awg+ui): stopped-container reads, honest connections count, phantom card after uninstall", base main, head leonidorlov-hash:deploy/v170, описание RU/EN. maintainer_can_modify=true.
- Открыто: дождаться реакции автора на #195; далее старые хвосты (bind-mount бэкап, NATA IPv6, self-service баг, спам логов).

## 28.09 ~21:50 — Проверка параллельной работы: порог CONN_WARN_THRESHOLD 600→900
- Чужая сессия: коммит 7a1d660 (только managers/awg_manager.py, порог+комментарий), PR #196 в апстрим (EN, open/clean), черри-пик в deploy/v160. Проверено: правка корректна, порог живёт только в awg_manager.py (242, 2696-2705), PR оформлен верно.
- НАЙДЕНА ОШИБКА в том логе: «заработает после pull на SERVERA» — неверно, т.к. прод на deploy/v170, а 7a1d660 был только в deploy/v160. Исправлено: cherry-pick в deploy/v170 (ee9dbf2), запушено — PR #195 теперь содержит 4 коммита (описание PR не упоминает порог — если что, дописать).
- Обновление SERVERA: ветка на сервере имеет ЛОКАЛЬНЫЕ SHA (425bdd7...), fast-forward невозможен → git fetch fork && git reset --hard fork/deploy/v170 && systemctl restart amnezia-panel.
- Выполнено: SERVERA на fork/deploy/v170 (ee9dbf2), рестарт сделан. Прод = v1.7.0 + 4 наших фикса (стопнутый контейнер, счётчик, фантомная карточка, порог 900). Теперь git pull --ff-only на SERVERA работает штатно.

## 28.09 ~22:15 — HANDOFF.md стал публичным каналом синхронизации чатов
- HANDOFF.md выведен из .git/info/exclude, в шапку добавлен протокол для любого AI-чата (читать перед работой, git = источник правды, писать после итерации, пушить сразу). Закоммичен в deploy/v160 (c8ecf60) и deploy/v170 (211a268).
- IP-адреса серверов вычищены (f8bd0f6 / 1128fa3): заменены на <IP:NATA>, <IP:SERVERA> и т.п.; имена серверов оставлены по решению владельца. ВНИМАНИЕ: IP остались в git-истории веток (полная зачистка = перепись истории, сломает ветку PR #195 — отложено до мержа).
- Паролей/ключей в HANDOFF нет и не должно появляться — правило навсегда: в файл пишем без секретов.
- Добавлен CHAT-RULES.md (короткая версия правил для соседних чатов) в обе ветки. HANDOFF растёт — периодически сливать старые записи в HANDOFF-ARCHIVE.md, чтобы чтение не жрало токены.

## 28.09 22:55 — Чат 22:42 введён в курс; запись 21:45 ОТМЕНЁНА
- Пользователь подтвердил: переход SERVERA на deploy/v170 28.09 — осознанный (апстрим v1.7.0). Запись 21:45 ниже («аномалия v170, откат на v160») — ОТМЕНЯЕТСЯ, исторический слепок ошибочного вывода. Факты про состав v170 на 19:51 верны, вывод неверен: автор 1.7.0 смержил наши #177/#178/#185 + чужие + security-пакет; «недостающие патчи» из v160 — это в основном открытые PR #163–#175/#196, а не потерянная работа.
- Текущий прод: fork/deploy/v170, HEAD ee9dbf2 = v1.7.0 + 4 наших фикса (стопнутый контейнер, счётчик External, фантомная карточка b80a025, порог 900). SERVERA обновлён (см. 21:50), git pull --ff-only там работает штатно.
- Будущее обновление SERVERA: git fetch fork && git reset --hard fork/deploy/v170 && systemctl restart amnezia-panel.
- Постоянные правила из чата 22:42 приняты (дублируют шапку + CHAT-RULES.md): читать HANDOFF целиком + git fetch/log перед работой; писать и коммитить сюда после каждой итерации; пушить сразу; без паролей/IP в файле; команды серверам — по одной, выполняет пользователь; перед записью git pull --ff-only.
- Заодно исправлены устаревшие строки: прод-ветка = deploy/v170, заметка «HANDOFF не коммитить» удалена, команда обновления SERVERA — под ремоты origin=апстрим/fork=форк.

## 29.09 10:55 — NATA: «External вместо имён пиров» вернулся (диагностика 39c155a, deploy/v170)
- Симптом (скриншот-текст от пользователя): список awg2 (81 пир) периодически показывает 13 пиров с именами + 68 «External (IP)». Привязки юзеров (👤), IP, трафик, рукопожатия у External корректны. Лечится 2–3 обновлениями страницы. Искажена часть списка, не весь.
- Ключевые факты из дампа: именованных РОВНО 13 — столько же, сколько пиров у соседнего инстанса 3.1 на том же сервере. У именованных НЕТ статистики wg show, у External — есть. Т.е. conf и wg-show читались с ПРАВИЛЬНОГО контейнера (amnezia-awg2, 81 пир), а clientsTable — будто бы с другого (13-записного).
- Анализ кода (deploy/v170): все пути чтения таблицы — all-or-error (transport: полный вывод или ("", -1); JSONDecodeError → drop batch + прямое перечитывание → RuntimeError). Партиальный-но-валидный JSON из обрезки получить нельзя. Фронт «External» сам не рисует (только бэкенд). Пул SSH общий, batch от /check TTL 15s, но разбор батча при обрезке даёт либо 0 имён, либо фолбэк на прямое чтение — не 13. _container_name чистая мапа, менеджеры создаются per-request. Единственная консистентная гипотеза: иногда читается ЦЕЛЫЙ clientsTable чужого контейнера; код-путь пока не найден — нужен ловец.
- Диагностика 39c155a: INFO-лог при каждом чтении таблицы (контейнер, путь prefetch/direct, число записей, байты) + сводка merge в get_clients (table=N, conf=M, External=K). 467 тестов OK (один прогон дал флаки-фейк, повторно 2× зелёно). Запушено в deploy/v170.
- Эксперимент подтверждения (выполнить на NATA): сравнить число записей clientsTable в amnezia-awg2 vs amnezia-awg3. Если у amnezia-awg3 ровно 13 — гипотеза «чужая таблица» подтверждена.
- Если гипотеза подтвердится, следующий шаг: искать, как _get_clients_table('awg2') может достать таблицу amnezia-awg3 (подозрение — общий пул SSH + _awg_batch, логи покажут путь).

## 29.09 13:25 — NATA External: бэкенд-ответ в момент сбоя ОК, экран — нет (проблема в двух слоях)
- Подтверждено пользователем: на NATA `amnezia-awg2: 71` записей в clientsTable, `amnezia-awg3: 13` — совпадение с числом «именованных» (13) на багованном экране.
- Консоль браузера ВО ВРЕМЯ сбоя: fetch /connections?protocol=awg2 → `named: 69 total: 71` (2 легитимных conf-only External). Т.е. бэкенд в тот момент ответил ПРАВИЛЬНО, а экран показывал 13 имён + 68 External (13+68=81 ≠ 71) — рендер из более раннего «плохого» ответа.
- Вывод: (1) КОРЕНЬ — бэкенд ИНОГДА отдаёт для awg2 таблицу awg3 (13 записей); транспортно «частично-валидный» ответ невозможен, код-путь не найден — ждём ловец 39c155a. (2) СИМПТОМ ВИСИТ — UI не перерисовывает список при последующих хороших ответах (peer-poll выключен по дефолту, авто-рефетча/плейсхолдера нет — идея из 22.09 не реализована).
- SERVERA: git pull --ff-only пользователя НЕ СРАБОТАЛ (на SERVERA origin=апстрим, tracking нет; заодно увидели: апстрим выпустил v1.7.1, тег 49c222b — не трогали). Правильная команда обновления: git fetch fork && git reset --hard fork/deploy/v170 && systemctl restart amnezia-panel. Ловец попадёт на сервер только после неё.
- СЛЕДУЮЩИЙ ШАГ: после рестарта, при следующем появлении External на экране: journalctl -u amnezia-panel -n 300 | grep -E "clientsTable|get_clients" — прислать строки.

## 29.09 13:45 — NATA External: ПОЙМАНО — отравленная prefetch-батч-запись, сторож 4d0db9f
- Журнал SERVERA (ловец 39c155a): `12:32:53 clientsTable amnezia-awg2: 13 records, 4872 bytes (via prefetch batch)` + `get_clients(awg2): table=13, conf peers total=80, External=68`. Ровно через секунду прямое чтение: `amnezia-awg3: 13 records, 4872 bytes` — БАЙТ-В-БАЙТ та же таблица. Т.е. батч-запись amnezia-awg2 = СМЕШАННАЯ: конфиг awg2 (80 пиров) + clientsTable amnezia-awg3 (13 записей). Direct-read пути при этом всегда чистые (71/81 записей).
- Дыра в парсере prefetch (line-based разбор @@CONTAINER@@/@@CLIENTS@@ маркеров) так и не воспроизведена статически: склейки маркеров дают невалидный JSON (→ фолбэк) или пустую секцию (→ 0 имён), но НЕ смешанную валидную пару. Гипотезы: гонка двух prefetch на одном пуловом SSH / нестандартный вывод docker exec. Не доказано — поэтому сторож на потреблении.
- ФИКС 4d0db9f (deploy/v170): integrity guard в _get_clients_table — паблики таблицы обязаны встречаться в конфе ТОЙ ЖЕ батч-записи; рассинхрон = выкинуть запись + прямое чтение (warning в лог). Плюс логирование сборки батча (размеры секций, байты вывода) — следующий «плохой» прогон покажет, что видел парсер. +1 регрессионный тест (poisoned batch → direct read), фикстура старого теста приведена к инварианту table⊆conf. 468 тестов OK.
- Второй слой (фронт держит старый плохой рендер, polling выкл.) пока не чинили — после сторожа бэкенд сам себя лечит, симптом должен перестать появляться. Если появится «13 имён + 0 External» (целая запись awg3 под ключом awg2) — guard его НЕ поймает (консистентная пара), смотреть лог prefetch section sizes.
- В журнале заодно замечено: awg2 table читался и 71, и 81 записью за минуты (пиры активно добавлялись — пользователь работал), awg3 — 4/18/13/5/8 (это РАЗНЫЕ СЕРВЕРА флота в общем логе, не аномалия). Поток get_clients каждые 1–2с идёт откуда-то при выключенном polling — НЕ исследовано (возможно открытые вкладки/модалки).
- Раскатка: git fetch fork && git reset --hard fork/deploy/v170 && systemctl restart amnezia-panel (после неё прислать свежий grep журнала при следующем срабатывании warning'а сторожа).
