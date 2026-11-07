-- =========================================================
-- JANAFIT PRODUCTION DATABASE SCHEMA FOR SUPABASE (PostgreSQL)
-- =========================================================

-- 1. Таблица уроков курса (можно менять ссылки на видео прямо здесь без кода!)
CREATE TABLE IF NOT EXISTS public.lessons (
    day INTEGER PRIMARY KEY,
    week INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    duration TEXT NOT NULL,
    focus TEXT,
    video_url TEXT NOT NULL,
    video_type TEXT DEFAULT 'youtube', -- 'youtube', 'telegram', 'kinescope'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Начальные данные для 7 дней (легко дополнить до 21 дня)
INSERT INTO public.lessons (day, week, title, duration, focus, video_url) VALUES
(1, 1, 'Пробуждение и лимфодренаж Full Body', '20 мин', 'Снятие утренней отечности, диафрагмальное дыхание', 'https://youtu.be/gC_L9qAHVJ8'),
(2, 1, 'Красивая осанка и здоровая спина', '22 мин', 'Раскрытие грудного отдела, укрепление лопаток', 'https://youtu.be/2MoGxae-zyo'),
(3, 1, 'Упругие ягодицы без нагрузки на колени', '25 мин', 'Изолированная проработка ягодичных мышц', 'https://youtu.be/I94V6qBfF0Y'),
(4, 1, 'Плоский живот и глубокие мышцы кора', '18 мин', 'Поперечная мышца живота, вакуум', 'https://youtu.be/ml6cT4AZdqI'),
(5, 1, 'Стройные ноги и подтянутые бедра', '24 мин', 'Внутренняя и задняя поверхность бедер', 'https://youtu.be/IT94xC35u6k'),
(6, 1, 'Мягкое кардио-жиросжигание (No Jumps)', '25 мин', 'Интервальное кардио без прыжков и нагрузки на суставы', 'https://youtu.be/UBMk30rjy0o'),
(7, 1, 'Глубокая растяжка, гибкость и релакс', '25 мин', 'Снятие мышечной усталости, удлинение мышц', 'https://youtu.be/enYITYwv8c4')
ON CONFLICT (day) DO UPDATE SET
    title = EXCLUDED.title,
    video_url = EXCLUDED.video_url;

-- 2. Таблица пользователей и лидов (полная база клиентов)
CREATE TABLE IF NOT EXISTS public.users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    has_access BOOLEAN DEFAULT FALSE,
    access_granted_at TIMESTAMP WITH TIME ZONE,
    workouts_completed_count INTEGER DEFAULT 0,
    food_scans_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Таблица оплат и чеков
CREATE TABLE IF NOT EXISTS public.payments (
    id BIGSERIAL PRIMARY KEY,
    invoice_id TEXT UNIQUE NOT NULL,
    user_id BIGINT REFERENCES public.users(user_id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    currency TEXT DEFAULT 'KZT',
    provider TEXT NOT NULL, -- 'robokassa', 'kaspi'
    status TEXT DEFAULT 'pending', -- 'pending', 'success', 'rejected'
    receipt_file_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Таблица пройденных тренировок
CREATE TABLE IF NOT EXISTS public.user_progress (
    user_id BIGINT REFERENCES public.users(user_id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    PRIMARY KEY (user_id, day)
);

-- 5. Таблица замеров тела (вес, талия, бедра)
CREATE TABLE IF NOT EXISTS public.user_measurements (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users(user_id) ON DELETE CASCADE,
    weight NUMERIC(5, 2),
    waist NUMERIC(5, 2),
    hips NUMERIC(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 6. Таблица сканирований еды и анализа рациона
CREATE TABLE IF NOT EXISTS public.user_meals (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES public.users(user_id) ON DELETE CASCADE,
    dish_name TEXT NOT NULL,
    calories INTEGER NOT NULL,
    protein NUMERIC(5, 1),
    fats NUMERIC(5, 1),
    carbs NUMERIC(5, 1),
    omega3_score INTEGER DEFAULT 25,
    greens_score INTEGER DEFAULT 30,
    vitamins_score INTEGER DEFAULT 50,
    advice TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Индексы для быстрой выборки
CREATE INDEX IF NOT EXISTS idx_users_has_access ON public.users(has_access);
CREATE INDEX IF NOT EXISTS idx_meals_user_id ON public.user_meals(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_user_id ON public.user_progress(user_id);
