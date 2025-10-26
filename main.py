import os
import pandas as pd
import numpy as np
import re
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
import plotly.graph_objects as go

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Цвета
MAIN_COLORS = ['blue', 'red', 'green', 'black', 'gray']
FILE_COLORS_ANALYTICAL = ['green', 'gray', 'black']
FUNC_COLORS = ['blue', 'red']

# Безопасное окружение для вычисления функций
SAFE_DICT = {
    "__builtins__": {},
    "np": np,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "pi": np.pi,
    "e": np.e
}

def safe_eval(expr, x_vals):
    try:
        expr = expr.replace('^', '**')
        expr = re.sub(r'\b(sin|cos|tan|exp|log|log10|sqrt|abs)\b', r'np.\1', expr)
        if not re.match(r'^[0-9+\-*/().,\s\w\s]+$', expr):
            raise ValueError("Недопустимые символы в формуле")
        SAFE_DICT['x'] = x_vals
        result = eval(expr, {"__builtins__": {}}, SAFE_DICT)
        result = np.array(result, dtype=np.float64)
        result = np.where(np.isinf(result) | np.isnan(result), np.nan, result)
        return result
    except Exception as e:
        raise ValueError(f"Ошибка в формуле: {e}")

# === Главная страница (основной режим) ===
@app.route('/', methods=['GET', 'POST'])
def index_page():
    plot_html = None
    error = None

    if request.method == 'POST':
        files = []
        connect_lines = []

        for i in range(1, 6):
            f = request.files.get(f'file{i}')
            if f and f.filename.endswith('.xlsx'):
                files.append(f)
                connect_lines.append(request.form.get(f'connect{i}') == 'on')
            elif f:
                error = "Все файлы должны иметь расширение .xlsx"
                break

        if not error:
            if not files:
                error = "Загрузите хотя бы один .xlsx файл"
            else:
                fig = go.Figure()
                success_count = 0
                x_axis_title = "X"
                y_axis_title = "Y"
                titles_set = False

                for idx, file in enumerate(files):
                    if idx >= 5:
                        break
                    try:
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)

                        df = pd.read_excel(filepath, header=0)
                        if df.shape[1] < 2:
                            error = f"Файл {filename}: нужно ≥2 столбцов"
                            continue

                        col_names = df.columns.tolist()
                        x_name = str(col_names[0]).strip()
                        y_name = str(col_names[1]).strip()

                        if "Unnamed" in x_name or x_name == "nan":
                            x_name = ""
                        if "Unnamed" in y_name or y_name == "nan":
                            y_name = ""

                        df_clean = df.dropna(subset=[df.columns[0], df.columns[1]])
                        if df_clean.empty:
                            continue

                        if not titles_set:
                            x_axis_title = x_name if x_name else "X"
                            y_axis_title = y_name if y_name else "Y"
                            titles_set = True

                        mode = 'lines+markers' if connect_lines[idx] else 'markers'
                        fig.add_trace(go.Scatter(
                            x=df_clean[df.columns[0]],
                            y=df_clean[df.columns[1]],
                            mode=mode,
                            name=filename,
                            line=dict(color=MAIN_COLORS[idx]),
                            marker=dict(color=MAIN_COLORS[idx], size=6)
                        ))
                        success_count += 1

                    except Exception as e:
                        error = f"Ошибка при обработке {file.filename}: {str(e)}"
                        continue

                if success_count == 0:
                    error = error or "Не удалось обработать ни один файл"
                else:
                    # Получаем название графика от пользователя
                    user_title = request.form.get('plot_title', '').strip()
                    if not user_title:
                        user_title = "График по загруженным файлам"

                    fig.update_layout(
                        title=user_title,
                        xaxis_title=x_axis_title,
                        yaxis_title=y_axis_title,
                        hovermode='x unified',
                        template='plotly_white',
                        legend_title="Файлы"
                    )
                    plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    return render_template('index.html', plot_html=plot_html, error=error)

# === Аналитический анализ ===
@app.route('/analytical', methods=['GET', 'POST'])
def analytical():
    plot_html = None
    error = None

    if request.method == 'GET':
        return render_template('analytical.html', plot_html=plot_html, error=error)

    # POST
    files = []
    for i in range(1, 4):
        f = request.files.get(f'file{i}')
        if f and f.filename.endswith('.xlsx'):
            files.append(f)
        elif f:
            error = "Все файлы должны быть .xlsx"
            break

    func1 = request.form.get('func1', '').strip()
    func2 = request.form.get('func2', '').strip()
    functions = []
    if func1:
        functions.append(func1)
    if func2:
        functions.append(func2)

    if not files and not functions:
        error = "Загрузите файлы или введите хотя бы одну функцию"

    if not error:
        fig = go.Figure()
        x_axis_title = "X"
        y_axis_title = "Y"
        titles_set = False
        all_x = []

        for idx, file in enumerate(files):
            if idx >= 3:
                break
            try:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                df = pd.read_excel(filepath, header=0)
                if df.shape[1] < 2:
                    error = f"Файл {filename}: нужно ≥2 столбцов"
                    continue

                col_names = df.columns.tolist()
                x_name = str(col_names[0]).strip()
                y_name = str(col_names[1]).strip()

                if "Unnamed" in x_name or x_name == "nan":
                    x_name = ""
                if "Unnamed" in y_name or y_name == "nan":
                    y_name = ""

                df_clean = df.dropna(subset=[df.columns[0], df.columns[1]])
                if df_clean.empty:
                    continue

                if not titles_set:
                    x_axis_title = x_name if x_name else "X"
                    y_axis_title = y_name if y_name else "Y"
                    titles_set = True

                all_x.extend(df_clean[df.columns[0]].tolist())

                fig.add_trace(go.Scatter(
                    x=df_clean[df.columns[0]],
                    y=df_clean[df.columns[1]],
                    mode='markers',
                    name=f"Файл {idx+1}: {filename}",
                    marker=dict(color=FILE_COLORS_ANALYTICAL[idx], size=6)
                ))
            except Exception as e:
                error = f"Ошибка файла {file.filename}: {str(e)}"
                continue

        if all_x:
            x_min, x_max = min(all_x), max(all_x)
        else:
            x_min, x_max = -10, 10
        x_dense = np.linspace(x_min, x_max, 500)

        for idx, expr in enumerate(functions):
            if idx >= 2:
                break
            try:
                y_vals = safe_eval(expr, x_dense)
                fig.add_trace(go.Scatter(
                    x=x_dense,
                    y=y_vals,
                    mode='lines',
                    name=f"Функция {idx+1}: {expr}",
                    line=dict(color=FUNC_COLORS[idx], width=2)
                ))
            except Exception as e:
                error = f"Ошибка в функции: {str(e)}"
                continue

        if not error:
            user_title = request.form.get('plot_title', '').strip()
            if not user_title:
                user_title = "Аналитический анализ"

            fig.update_layout(
                title=user_title,
                xaxis_title=x_axis_title,
                yaxis_title=y_axis_title,
                hovermode='x unified',
                template='plotly_white',
                legend_title="Данные и функции"
            )
            plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    return render_template('analytical.html', plot_html=plot_html, error=error)

# === Инструкция ===
@app.route('/instruktion')
def instruktion():
    return render_template('instruktion.html')

# === Запуск сервера ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)