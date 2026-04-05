# Сборка и развёртывание для разработки

## Требования

- **Python** 3.8+ (на Windows удобно через `py -3`)
- **Node.js** + **npm** (для сборки веб-интерфейса `aw-webui`)
- **Inno Setup 6** — только для сборки установщика Windows (`ISCC.exe`)
- Репозиторий с подмодулями / пакетами: `aw-core`, `aw-client`, `aw-server`, `aw-qt`, вотчеры и т.д. (как в вашем дереве проекта)

## Быстрый старт (разработка без установщика)

### 1. Зависимости Python (editable)

Из корня репозитория (пути подставьте свои):

```powershell
py -3 -m pip install -e .\aw-core -e .\aw-client -e .\aw-server
```

Для трея и GUI:

```powershell
py -3 -m pip install -e "PyQt6==6.5.3" "PyQt6-Qt6==6.5.3" PyQt6-sip click setuptools
py -3 -m pip install -e .\aw-qt
```

Вотчеры (по необходимости):

```powershell
py -3 -m pip install -e .\aw-watcher-afk -e .\aw-watcher-window
```

### 2. Сборка веб-интерфейса `aw-server`

```powershell
cd aw-server\aw-webui
npm install
npm run build
```

Статика копируется в `aw-server/aw_server/static` (скрипт установщика делает это автоматически; вручную при отладке — см. `scripts/package/build-windows-installer.ps1`).

### 3. Запуск сервера

```powershell
cd aw-server
py -3 -m aw_server
```

Или после `pip install -e`: `aw-server` в PATH. API: `http://localhost:5600`, UI: тот же хост.

### 4. Запуск `aw-qt` (трей)

Из корня, с установленным `aw-qt`:

```powershell
py -3 -m aw_qt
```

Либо `aw-qt.exe` из каталога сборки. Для второго экземпляра при отладке: переменная окружения `AW_ALLOW_MULTIPLE_INSTANCES=1`.

## Сборка установщика Windows (.exe)

Полный сценарий: PyInstaller для модулей + Inno Setup.

```powershell
pwsh -File scripts\package\build-windows-installer.ps1
```

Если `pwsh` нет:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\package\build-windows-installer.ps1
```

Требования скрипта: `py -3`, `npm`, `ISCC.exe` (Inno Setup; в скрипте можно задать `INNO_SETUP_ISCC`).

Результат: `dist\activitywatch-<version>-windows-setup.exe` (версия берётся из `pyproject.toml`). Каталог `dist/` в `.gitignore` — артефакты в репозиторий не коммитятся.

## Дефолты центрального сервера (GFP/TIM)

Значения по умолчанию до появления `settings.json` задаются в **`aw-server/aw_server/settings.py`** в словаре **`CENTRAL_DEFAULTS`** (ключи API: `gfpsEnabled`, `gfpsServerIP`, `gfpsServerPort`).

Для согласованности первого кадра UI см. начальное состояние в **`aw-server/aw-webui/src/stores/settings.ts`**.

После сохранения настроек в приложении значения хранятся в конфиге aw-server (каталог данных ActivityWatch), дефолты из кода на уже сохранённые ключи не влияют.

## Логи

- **aw-server**: файловый лог + stderr (см. `aw_server/main.py`, `aw_core.log`).
- **aw-qt**: логирование через `aw_core.log` (папка логов в меню трея).

## Полезные переменные окружения

| Переменная | Назначение |
|------------|------------|
| `AW_ALLOW_MULTIPLE_INSTANCES=1` | Разрешить несколько процессов `aw-qt` (только отладка) |
| `LOG_LEVEL=DEBUG` | Подробные логи (если поддерживается компонентом) |
