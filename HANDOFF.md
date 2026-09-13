# HANDOFF — Amnezia-Web-Panel (форк leonidorlov-hash)

Обновлено: 2026-09-13. Репо: `C:\KIMI\panele4ka\ПанелечкаПроект` (сам git-репо прямо в этой папке, venv в `./venv`).

## Среда
- `origin` = форк `leonidorlov-hash/Amnezia-Web-Panel` (пушим сюда), `upstream` = `PRVTPRO/Amnezia-Web-Panel`.
- Прод-ветка пользователя: `deploy/v160` (на серверах SERVERA и др.).
- identity уже стоит локально в репо (user.name/email leonidorlov-hash).
- Тесты: `venv/Scripts/python.exe -m unittest discover -s tests` (268 тестов, 1 skip = playwright).
- GitHub API токен: `$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | grep '^password=' | cut -d= -f2)`. MCP github тоже жив.
- Git Bash: `cd` не сохраняется между Bash-вызовами — каждая команда начинается с `cd "/c/KIMI/panele4ka/ПанелечкаПроект" &&`.

## Открытые PR в апстриме (все CI green, 2026-09-13)
- #163 fix(ssh): sudo-пароль через stdin — ветка `fix/sudo-password-stdin`
- #165 feat(awg): IPv6 DNS (DNS6) — `feat/dns6`
- #166 feat(users): отвязка ✂️ + диплинки — `feat/unlink-deeplink` (var currentConnsUserId!)
- #167 feat(users): linking UX (мультивыбор, no-reload, анти-дубль) — `feat/link-ux` (var там же!)
- #168 fix(users): get_clients через _manager_call + ключи i18n — `fix/clients-and-i18n`
- #169 feat(users): богатые карточки + лампочка юзера — `feat/users-rich-cards` (стек на #166)
- #170 feat(server): привязка из редактора пира + мелочи — `feat/peer-editor-link` (стек на #169)

Порядок мержа стека: #166 → #169 → #170. Остальные независимы.
ВАЖНО: в #166 и #167 объявления `var currentConnsUserId/Username` (не let) — иначе дубль `let` после мержа обоих = SyntaxError. Не менять обратно!

## Проверка полноты (2026-09-13)
`pr-union` (локальная тестовая ветка = все 7 PR поверх upstream/main) ≈ deploy/v160.
Расхождения только позиционные/косметические + union НОВЕЕ deploy (var-фикс, guard от невалидного protocol в диплинке, no-popup при линковке). Т.е. всё рабочее из deploy отправлено в PR.
Не пересобирать pr-union вручную без необходимости; конфликты переводов разруливались union-merge JSON (ours.update(theirs)).

## Уже смержено автором
Все 32 прошлых PR (#68…#152), включая #150 (лампочки/черепаха/спиннеры), #151 (vendor CDN), #152 (роли), #141 (IPAM), #134 (импорт wg-easy).

## Серверы пользователя
- SERVERA = root@stockholmservera, панель `/root/Amnezia-Web-Panel`, обновление: `cd /root/Amnezia-Web-Panel && git pull --ff-only && systemctl restart amnezia-panel`
- OVH = debian@vps-c27e7981, `/home/debian/Amnezia-Web-Panel`, systemctl через sudo
- mamkam — панель удалена 2026-09-07 (управляется через SERVERA)
- NATA (95.81.112.162, ssh :1803) — 13.09 лежал, вешал панель event-loop'ом (синхронный paramiko). Идея circuit breaker/per-server таймаутов предложена, пользователь не ответил.

## Незакрытые вопросы
- Circuit breaker для лежачих серверов (не утверждено).
- Автообновление панелей до новых релизов автора — по запросу пользователя.
