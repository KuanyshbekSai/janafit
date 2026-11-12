/**
 * ============================================================================
 * JANAFIT — GOOGLE APPS SCRIPT DATABASE BACKEND (CRM & CONTENT SYSTEM)
 * ============================================================================
 * Поддерживает 4 листа:
 * 1. "Пользователи" — база лидов, профили, замеры, количество тренировок и блюд.
 * 2. "Оплаты" — история платежей, чеки, статусы заказов.
 * 3. "Уроки" — 21 день тренировок со ссылками на видео, описанием и таймингами.
 * 4. "Дневник питания" — история всех отсканированных (фото/голос) приемов пищи.
 *
 * ИНСТРУКЦИЯ ПО ДЕПЛОЮ:
 * 1. Создайте новую Google Таблицу (sheets.new).
 * 2. В меню выберите: Расширения -> Apps Script.
 * 3. Вставьте этот код в файл Code.gs и сохраните (Ctrl+S / Cmd+S).
 * 4. Нажмите "Развернуть" (Deploy) -> "Новое развертывание" (New deployment).
 * 5. Тип: "Веб-приложение" (Web app).
 * 6. Описание: "Janafit API".
 * 7. Выполнять от имени: "Я" (Ваш аккаунт).
 * 8. У кого есть доступ: "Все" (Anyone).
 * 9. Скопируйте полученный URL (https://script.google.com/macros/s/.../exec)
 *    и вставьте его в файл .env или настройки Vercel: GAS_WEBAPP_URL="скопированный_URL".
 * ============================================================================
 */

const SHEET_USERS = "Пользователи";
const SHEET_PAYMENTS = "Оплаты";
const SHEET_LESSONS = "Уроки";
const SHEET_MEALS = "Дневник питания";
const SPREADSHEET_ID = "1SZcSpC5n59SI5Ei7TMy2KPpAHo4Y_xuQQ4lhU941_BA";

/**
 * Проверка общего секрета с сервером (Script Properties → GAS_SECRET).
 * Тот же секрет задаётся в переменной окружения GAS_SECRET на сервере.
 * Пока свойство не задано, проверка пропускается (обратная совместимость).
 */
function isAuthorized(provided) {
  const expected = PropertiesService.getScriptProperties().getProperty("GAS_SECRET");
  if (!expected) return true;
  return String(provided || "") === expected;
}

function getSS() {
  if (SPREADSHEET_ID && SPREADSHEET_ID.trim()) {
    try {
      return SpreadsheetApp.openById(SPREADSHEET_ID.trim());
    } catch (e) {
      console.warn("Could not open by ID, falling back to active: " + e);
    }
  }
  return SpreadsheetApp.getActiveSpreadsheet();
}

// Добавляем удобное меню при открытии таблицы
function onOpen() {
  try {
    SpreadsheetApp.getUi()
      .createMenu("🌸 Janafit Управление")
      .addItem("✨ Инициализировать все листы и структуру", "setupJanafitSheets")
      .addItem("🎬 Заполнить список 21 урока (базовый шаблон)", "seedLessons")
      .addToUi();
  } catch (e) {}
}

/**
 * Инициализация всех 4 листов со стилизованными заголовками и авто-шириной
 */
function setupJanafitSheets() {
  const ss = getSS();

  // 1. Лист Пользователи
  let usersSheet = ss.getSheetByName(SHEET_USERS) || ss.insertSheet(SHEET_USERS);
  if (usersSheet.getLastRow() === 0) {
    const headers = [
      "User ID", "Имя / Никнейм", "Username", "Доступ (VIP)", "Цель",
      "Рост (см)", "Вес (кг)", "Целевой вес (кг)", "Талия (см)", "Бёдра (см)",
      "Пройдено тренировок", "Отсканировано блюд", "Дата регистрации", "Последняя активность"
    ];
    usersSheet.appendRow(headers);
    formatHeaderRow(usersSheet, 14, "#ec4899");
  }

  // 2. Лист Оплаты
  let paySheet = ss.getSheetByName(SHEET_PAYMENTS) || ss.insertSheet(SHEET_PAYMENTS);
  if (paySheet.getLastRow() === 0) {
    const headers = ["ID Заказа (InvId)", "User ID", "Сумма (₸ / ₽)", "Статус", "Платежная система", "Дата и время"];
    paySheet.appendRow(headers);
    formatHeaderRow(paySheet, 6, "#8b5cf6");
  }

  // 3. Лист Уроки
  let lessonsSheet = ss.getSheetByName(SHEET_LESSONS) || ss.insertSheet(SHEET_LESSONS);
  if (lessonsSheet.getLastRow() === 0) {
    const headers = ["День", "Название тренировки", "Ссылка на видео", "Длительность (мин)", "Фокус зоны", "Описание"];
    lessonsSheet.appendRow(headers);
    formatHeaderRow(lessonsSheet, 6, "#ec4899");
    seedLessons();
  }

  // 4. Лист Дневник питания
  let mealsSheet = ss.getSheetByName(SHEET_MEALS) || ss.insertSheet(SHEET_MEALS);
  if (mealsSheet.getLastRow() === 0) {
    const headers = [
      "Дата и время", "User ID", "Название блюда", "Способ ввода (Фото/Голос)",
      "Калории (ккал)", "Белки (г)", "Жиры (г)", "Углеводы (г)", "Оценка (1-10)", "Совет нутрициолога"
    ];
    mealsSheet.appendRow(headers);
    formatHeaderRow(mealsSheet, 10, "#10b981");
  }

  try {
    ss.toast("Все листы Janafit успешно настроены!", "Успех ✅", 5);
  } catch (e) {}
}

function formatHeaderRow(sheet, numCols, bgColor) {
  const range = sheet.getRange(1, 1, 1, numCols);
  range.setBackground(bgColor);
  range.setFontColor("#ffffff");
  range.setFontWeight("bold");
  range.setHorizontalAlignment("center");
  sheet.setFrozenRows(1);
  for (let c = 1; c <= numCols; c++) {
    sheet.autoResizeColumn(c);
  }
}

/**
 * Заполняет 21 тренировку видеоуроками и описаниями
 */
function seedLessons() {
  const ss = getSS();
  const sheet = ss.getSheetByName(SHEET_LESSONS);
  if (!sheet) return;

  if (sheet.getLastRow() > 1) {
    return; // Уроки уже заполнены
  }

  const initialLessons = [
    [1, "Мягкий старт: Пробуждение тела и осанка", "https://assets.mixkit.co/videos/preview/mixkit-woman-doing-warm-up-exercises-in-a-gym-42774-large.mp4", 25, "Осанка, мобильность суставов", "Активация глубоких мышц кора и снятие спазма с шеи."],
    [2, "Упругие ягодицы и бедра без нагрузки на колени", "https://assets.mixkit.co/videos/preview/mixkit-woman-doing-squats-in-a-gym-42777-large.mp4", 28, "Ягодицы, задняя поверхность бедра", "Техника изоляции ягодичной мышцы и лимфодренаж."],
    [3, "Плоский живот и глубокий кор: Вакуум и пилатес", "https://assets.mixkit.co/videos/preview/mixkit-woman-exercising-in-a-bright-room-42772-large.mp4", 26, "Поперечная мышца живота, тазовое дно", "Безопасная работа с мышцами пресса без скручиваний."],
    [4, "Активное жиросжигание Low-Impact (без прыжков)", "https://assets.mixkit.co/videos/preview/mixkit-woman-doing-stretching-exercises-on-a-mat-42779-large.mp4", 30, "Всё тело, кардио-выносливость", "Интервальное ускорение метаболизма."],
    [5, "Красивые руки, ключицы и изящная спина", "https://assets.mixkit.co/videos/preview/mixkit-woman-doing-warm-up-exercises-in-a-gym-42774-large.mp4", 24, "Спина, трицепс, плечевой пояс", "Укрепление осанки и снятие сутулости."],
    [6, "Мягкая растяжка, шпагат и мобильность ТБС", "https://assets.mixkit.co/videos/preview/mixkit-woman-doing-stretching-exercises-on-a-mat-42779-large.mp4", 32, "Гибкость, расслабление", "Снятие напряжения с поясницы и раскрытие таза."],
    [7, "Восстановление и детокс: Лимфодренажный комплекс", "https://assets.mixkit.co/videos/preview/mixkit-woman-exercising-in-a-bright-room-42772-large.mp4", 22, "Лимфоток, снятие отечности", "Утренний комплекс против задержки жидкости."]
  ];

  for (let d = 8; d <= 21; d++) {
    initialLessons.push([
      d,
      `День ${d}: Прогрессия рельефа и тонуса`,
      "https://assets.mixkit.co/videos/preview/mixkit-woman-doing-warm-up-exercises-in-a-gym-42774-large.mp4",
      28,
      "Всё тело, тонус",
      `Продвинутый комплекс тренировки дня ${d} для закрепления стройности.`
    ]);
  }

  sheet.getRange(2, 1, initialLessons.length, 6).setValues(initialLessons);
}

/**
 * ============================================================================
 * HTTP API — doGet (Чтение данных: уроки, пользователи, питание)
 * ============================================================================
 */
function doGet(e) {
  try {
    const params = e ? e.parameter : {};
    const action = params.action || "ping";
    const ss = getSS();

    if (action === "ping") {
      return jsonResponse({ status: "ok", app: "Janafit GAS CRM Engine", time: new Date() });
    }

    if (!isAuthorized(params.secret)) {
      return jsonResponse({ status: "error", message: "unauthorized" });
    }

    // Получение списка всех уроков со ссылками на видео
    if (action === "getLessons") {
      const sheet = ss.getSheetByName(SHEET_LESSONS);
      if (!sheet) return jsonResponse({ status: "error", message: "Лист Уроки не найден" });
      const rows = sheet.getDataRange().getValues();
      const headers = rows[0];
      const lessons = [];
      for (let i = 1; i < rows.length; i++) {
        lessons.push({
          day: rows[i][0],
          title: rows[i][1],
          video_url: rows[i][2],
          duration: rows[i][3],
          focus: rows[i][4],
          description: rows[i][5]
        });
      }
      return jsonResponse({ status: "ok", lessons: lessons });
    }

    // Получение информации о пользователе
    if (action === "getUser") {
      const userId = Number(params.user_id);
      const sheet = ss.getSheetByName(SHEET_USERS);
      if (!sheet) return jsonResponse({ status: "error", message: "Лист Пользователи не найден" });
      const rows = sheet.getDataRange().getValues();
      for (let i = 1; i < rows.length; i++) {
        if (Number(rows[i][0]) === userId) {
          return jsonResponse({
            status: "ok",
            user: {
              user_id: rows[i][0],
              name: rows[i][1],
              username: rows[i][2],
              has_access: rows[i][3] === "VIP" || rows[i][3] === true,
              goal: rows[i][4],
              height: rows[i][5],
              weight: rows[i][6],
              target_weight: rows[i][7],
              waist: rows[i][8],
              hips: rows[i][9],
              workouts_completed: rows[i][10],
              meals_logged: rows[i][11]
            }
          });
        }
      }
      return jsonResponse({ status: "not_found", message: "Пользователь не найден" });
    }

    // Получение дневника питания пользователя
    if (action === "getMeals") {
      const userId = Number(params.user_id);
      const sheet = ss.getSheetByName(SHEET_MEALS);
      if (!sheet) return jsonResponse({ status: "ok", meals: [] });
      const rows = sheet.getDataRange().getValues();
      const meals = [];
      for (let i = 1; i < rows.length; i++) {
        if (userId && Number(rows[i][1]) === userId) {
          meals.push({
            created_at: rows[i][0],
            user_id: rows[i][1],
            dish_name: rows[i][2],
            input_type: rows[i][3],
            calories: rows[i][4],
            protein: rows[i][5],
            fats: rows[i][6],
            carbs: rows[i][7],
            health_score: rows[i][8],
            advice: rows[i][9]
          });
        }
      }
      return jsonResponse({ status: "ok", meals: meals });
    }

    return jsonResponse({ status: "error", message: "Неизвестный action" });
  } catch (err) {
    return jsonResponse({ status: "error", error: err.toString() });
  }
}

/**
 * ============================================================================
 * HTTP API — doPost (Синхронизация пользователей, оплат, питания, тренировок)
 * ============================================================================
 */
function doPost(e) {
  try {
    let payload = {};
    if (e && e.postData && e.postData.contents) {
      try {
        payload = JSON.parse(e.postData.contents);
      } catch (ex) {
        payload = e.parameter || {};
      }
    } else if (e && e.parameter) {
      payload = e.parameter;
    }

    if (!isAuthorized(payload.secret)) {
      return jsonResponse({ status: "error", message: "unauthorized" });
    }

    const action = payload.action;
    const ss = getSS();

    // 1. Синхронизация / создание пользователя
    if (action === "syncUser") {
      const sheet = ss.getSheetByName(SHEET_USERS) || ss.insertSheet(SHEET_USERS);
      const userId = Number(payload.user_id);
      const rows = sheet.getDataRange().getValues();
      let rowIndex = -1;

      for (let i = 1; i < rows.length; i++) {
        if (Number(rows[i][0]) === userId) {
          rowIndex = i + 1; // 1-based index in Sheets
          break;
        }
      }

      const nowStr = Utilities.formatDate(new Date(), "GMT+5", "yyyy-MM-dd HH:mm:ss");

      if (rowIndex > -1) {
        // Обновляем существующего
        if (payload.name) sheet.getRange(rowIndex, 2).setValue(payload.name);
        if (payload.username) sheet.getRange(rowIndex, 3).setValue(payload.username);
        if (payload.has_access !== undefined) sheet.getRange(rowIndex, 4).setValue(payload.has_access ? "VIP" : "Демо");
        if (payload.goal) sheet.getRange(rowIndex, 5).setValue(payload.goal);
        if (payload.height) sheet.getRange(rowIndex, 6).setValue(payload.height);
        if (payload.current_weight) sheet.getRange(rowIndex, 7).setValue(payload.current_weight);
        if (payload.target_weight) sheet.getRange(rowIndex, 8).setValue(payload.target_weight);
        if (payload.waist) sheet.getRange(rowIndex, 9).setValue(payload.waist);
        if (payload.hips) sheet.getRange(rowIndex, 10).setValue(payload.hips);
        if (payload.workouts_completed !== undefined) sheet.getRange(rowIndex, 11).setValue(payload.workouts_completed);
        if (payload.meals_logged !== undefined) sheet.getRange(rowIndex, 12).setValue(payload.meals_logged);
        sheet.getRange(rowIndex, 14).setValue(nowStr);
      } else {
        // Добавляем нового
        sheet.appendRow([
          userId,
          payload.name || "Участница",
          payload.username || "",
          payload.has_access ? "VIP" : "Демо",
          payload.goal || "Сбросить вес",
          payload.height || 168,
          payload.current_weight || 65,
          payload.target_weight || 58,
          payload.waist || 72,
          payload.hips || 98,
          payload.workouts_completed || 0,
          payload.meals_logged || 0,
          nowStr,
          nowStr
        ]);
      }
      return jsonResponse({ status: "ok", message: "User synced" });
    }

    // 2. Логирование оплаты
    if (action === "savePayment") {
      const sheet = ss.getSheetByName(SHEET_PAYMENTS) || ss.insertSheet(SHEET_PAYMENTS);
      const nowStr = Utilities.formatDate(new Date(), "GMT+5", "yyyy-MM-dd HH:mm:ss");
      sheet.appendRow([
        payload.inv_id || "INV-" + Date.now(),
        payload.user_id,
        payload.sum || 4990,
        payload.status || "PAID",
        payload.system || "Robokassa",
        nowStr
      ]);

      // Активируем статус VIP в таблице пользователей
      const userSheet = ss.getSheetByName(SHEET_USERS);
      if (userSheet && payload.user_id) {
        const uRows = userSheet.getDataRange().getValues();
        for (let i = 1; i < uRows.length; i++) {
          if (Number(uRows[i][0]) === Number(payload.user_id)) {
            userSheet.getRange(i + 1, 4).setValue("VIP");
            break;
          }
        }
      }
      return jsonResponse({ status: "ok", message: "Payment logged" });
    }

    // 3. Запись приема пищи (Фото или Голос)
    if (action === "logMeal") {
      const sheet = ss.getSheetByName(SHEET_MEALS) || ss.insertSheet(SHEET_MEALS);
      const nowStr = Utilities.formatDate(new Date(), "GMT+5", "yyyy-MM-dd HH:mm:ss");
      sheet.appendRow([
        nowStr,
        payload.user_id,
        payload.dish_name || "Блюдо",
        payload.input_type || "Фото",
        payload.calories || 0,
        payload.protein || 0,
        payload.fats || 0,
        payload.carbs || 0,
        payload.health_score || 9,
        payload.advice || ""
      ]);

      // Инкрементируем счетчик еды в таблице пользователей
      const userSheet = ss.getSheetByName(SHEET_USERS);
      if (userSheet && payload.user_id) {
        const uRows = userSheet.getDataRange().getValues();
        for (let i = 1; i < uRows.length; i++) {
          if (Number(uRows[i][0]) === Number(payload.user_id)) {
            const currentCount = Number(uRows[i][11]) || 0;
            userSheet.getRange(i + 1, 12).setValue(currentCount + 1);
            userSheet.getRange(i + 1, 14).setValue(nowStr);
            break;
          }
        }
      }
      return jsonResponse({ status: "ok", message: "Meal logged" });
    }

    // 3b. Удаление приёма пищи (последняя совпадающая запись пользователя)
    if (action === "deleteMeal") {
      const sheet = ss.getSheetByName(SHEET_MEALS);
      if (sheet) {
        const rows = sheet.getDataRange().getValues();
        for (let i = rows.length - 1; i >= 1; i--) {
          if (Number(rows[i][1]) === Number(payload.user_id) &&
              String(rows[i][2]) === String(payload.dish_name) &&
              Number(rows[i][4]) === Number(payload.calories || 0)) {
            sheet.deleteRow(i + 1);
            break;
          }
        }
      }
      return jsonResponse({ status: "ok", message: "Meal deleted" });
    }

    // 4. Отметка о пройденной тренировке
    if (action === "logWorkout") {
      const userSheet = ss.getSheetByName(SHEET_USERS);
      const nowStr = Utilities.formatDate(new Date(), "GMT+5", "yyyy-MM-dd HH:mm:ss");
      if (userSheet && payload.user_id) {
        const uRows = userSheet.getDataRange().getValues();
        for (let i = 1; i < uRows.length; i++) {
          if (Number(uRows[i][0]) === Number(payload.user_id)) {
            const curWorkouts = Number(uRows[i][10]) || 0;
            userSheet.getRange(i + 1, 11).setValue(curWorkouts + 1);
            userSheet.getRange(i + 1, 14).setValue(nowStr);
            break;
          }
        }
      }
      return jsonResponse({ status: "ok", message: "Workout logged" });
    }

    return jsonResponse({ status: "error", message: "Action not recognized" });
  } catch (err) {
    return jsonResponse({ status: "error", error: err.toString() });
  }
}

function jsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
