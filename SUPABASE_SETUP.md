# ⚡ Настройка Supabase за 2 минуты

Простая инструкция по настройке базы данных для синхронизации между устройствами.

## Почему Supabase проще Firebase?

✅ Регистрация через GitHub в 1 клик
✅ Всего 2 параметра вместо 6
✅ Создание проекта за 30 секунд
✅ Автоматическая настройка безопасности
✅ PostgreSQL база данных (надежнее NoSQL)

---

## Шаг 1: Создание проекта (30 секунд)

1. Откройте https://supabase.com
2. Нажмите **Start your project**
3. Войдите через **GitHub** (или создайте аккаунт)
4. Нажмите **New Project**
5. Заполните:
   - **Name**: `3d-printer-calc` (или любое название)
   - **Database Password**: придумайте надежный пароль (сохраните его!)
   - **Region**: выберите ближайший регион (например, `Frankfurt` для Европы)
6. Нажмите **Create new project**
7. Подождите ~30 секунд пока проект создается ☕

---

## Шаг 2: Получение ключей (10 секунд)

1. В левом меню внизу нажмите **⚙️ Settings**
2. Выберите **API**
3. Найдите раздел **Project API keys**
4. Скопируйте:
   - **Project URL** (например: `https://xxx.supabase.co`)
   - **Publishable API Key** (начинается с `sb_publishable_...`)

⚠️ **Важно:** НЕ используйте `secret` ключ - он только для сервера!

---

## Шаг 3: Вставка конфигурации (20 секунд)

### Вариант A: Через GitHub (рекомендуется)

1. Откройте файл на GitHub: https://github.com/Holymoly322/3d-printer-calculator/blob/master/index.html
2. Нажмите кнопку редактирования (карандаш)
3. Найдите строки 29-30:
```javascript
const SUPABASE_URL = "YOUR_SUPABASE_URL";
const SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY";
```
4. Замените на ваши значения:
```javascript
const SUPABASE_URL = "https://ваш-проект.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_ваш_ключ";
```
5. Нажмите **Commit changes**

### Вариант B: Локально

1. Откройте `index.html` в текстовом редакторе
2. Найдите строки 29-30
3. Вставьте ваши ключи
4. Сохраните файл
5. Выполните:
```bash
git add index.html
git commit -m "Add Supabase configuration"
git push
```

---

## Шаг 4: Создание таблиц (1 минута)

1. В Supabase откройте **SQL Editor** (слева в меню, иконка `</>`)
2. Нажмите **New query**
3. Скопируйте и вставьте этот SQL код:

```sql
-- Создание таблиц
CREATE TABLE printer_settings (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  printer_cost DECIMAL DEFAULT 50000,
  amortization_months INTEGER DEFAULT 24,
  electricity_cost DECIMAL DEFAULT 6,
  printer_power DECIMAL DEFAULT 0.3,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE spools (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  cost DECIMAL NOT NULL,
  weight DECIMAL NOT NULL,
  price_per_gram DECIMAL NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE prints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  name TEXT NOT NULL,
  spool_name TEXT NOT NULL,
  weight DECIMAL NOT NULL,
  hours DECIMAL NOT NULL,
  sale_price DECIMAL NOT NULL,
  material_cost DECIMAL NOT NULL,
  electricity_cost_calc DECIMAL NOT NULL,
  amortization DECIMAL NOT NULL,
  total_cost DECIMAL NOT NULL,
  profit DECIMAL NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security (каждый пользователь видит только свои данные)
ALTER TABLE printer_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE spools ENABLE ROW LEVEL SECURITY;
ALTER TABLE prints ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own settings" ON printer_settings
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own spools" ON spools
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own prints" ON prints
  FOR ALL USING (auth.uid() = user_id);
```

4. Нажмите **Run** (или Ctrl+Enter)
5. Должно появиться: **"Success. No rows returned"** ✅

---

## Шаг 5: Готово! 🎉

Откройте приложение: https://holymoly322.github.io/3d-printer-calculator/

1. Зарегистрируйтесь с вашим email
2. Начните добавлять данные
3. Войдите с другого устройства под тем же email
4. Все данные синхронизированы!

---

## 🔐 Безопасность

✅ **Row Level Security (RLS)** - каждый пользователь видит только свои данные
✅ **Пароли хешируются** - Supabase использует bcrypt
✅ **HTTPS** - все данные передаются по защищенному каналу
✅ **JWT токены** - безопасная авторизация

---

## 💰 Бесплатные лимиты Supabase

- ✅ 500 MB базы данных
- ✅ 1 GB file storage
- ✅ 2 GB bandwidth
- ✅ 50,000 monthly active users
- ✅ Unlimited API requests

**Для личного использования более чем достаточно!**

---

## 🆘 Troubleshooting

### Ошибка "Invalid API key"
- Проверьте что скопировали **Publishable** ключ (не secret)
- Убедитесь что ключ вставлен полностью

### Ошибка "relation does not exist"
- Выполните SQL запрос из Шага 4
- Проверьте что все таблицы созданы в **Table Editor**

### Данные не синхронизируются
- Проверьте что вы вошли под одним email на всех устройствах
- Откройте консоль браузера (F12) и проверьте ошибки

### Не могу зарегистрироваться
- Проверьте почту - возможно нужно подтвердить email
- В Supabase: **Authentication** → **Settings** → отключите "Confirm email"

---

**Нужна помощь?** Создайте Issue: https://github.com/Holymoly322/3d-printer-calculator/issues
