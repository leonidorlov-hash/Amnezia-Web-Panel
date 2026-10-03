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
