"""Оконное приложение; алгоритм загружается из того же блокнота."""
import argparse
import json
from pathlib import Path
import sys
import threading


def run(input_file, output_file, max_qty=6, distance=1):
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    notebook = json.loads((base / 'shlop.ipynb').read_text(encoding='utf-8'))
    namespace = {}
    code = next(''.join(c['source']) for c in notebook['cells']
                if c['cell_type'] == 'code' and 'def optimize_whole_bins(' in ''.join(c['source']))
    exec(compile(code, 'shlop.ipynb', 'exec'), namespace)
    pd = namespace['pd']
    if Path(input_file).resolve() == Path(output_file).resolve():
        raise ValueError('Выберите другой файл результата: исходный файл нельзя перезаписывать.')
    original = pd.read_excel(input_file)
    bad_bins = set(original.loc[pd.to_numeric(original['Количество'], errors='raise') < 0, 'Тара'])
    invalid = original[original['Тара'].isin(bad_bins)]
    valid = original[~original['Тара'].isin(bad_bins)]
    result, freed, stats, groups = namespace['optimize_whole_bins'](
        valid, max_small_qty=max_qty, max_street_distance=distance)
    report = namespace['create_consolidation_report'](result, groups)
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for name, frame in [('Товары', result), ('План перемещений', report),
                            ('Требуют сверки', invalid), ('Статистика', pd.DataFrame([stats]))]:
            frame.to_excel(writer, sheet_name=name, index=False)
    return stats, len(bad_bins)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', nargs=2, metavar=('INPUT', 'OUTPUT'))
    args = parser.parse_args()
    if args.smoke_test:
        run(*args.smoke_test)
        return
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('Схлопывание тар')
    root.geometry('540x300')
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Приоритет: код → группа → сектор', font=('', 12)).pack(anchor='w')
    ttk.Label(frame, text='Один этаж. Заполнение по долям вместимости товаров.').pack(anchor='w', pady=8)
    ttk.Label(frame, text='Максимум единиц в переносимой таре:').pack(anchor='w')
    qty = ttk.Entry(frame)
    qty.insert(0, '6')
    qty.pack(fill='x')
    ttk.Label(frame, text='Расстояние между улицами (0 — одна, 1 — соседние):').pack(anchor='w', pady=(8, 0))
    distance = ttk.Entry(frame)
    distance.insert(0, '1')
    distance.pack(fill='x')
    status = tk.StringVar(value='Выберите исходный Excel-файл кнопкой ниже.')
    def start():
        try:
            q, d = int(qty.get()), int(distance.get())
            if q <= 0 or d < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror('Настройки', 'Количество — целое число > 0, расстояние — целое число >= 0.')
            return
        source = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if not source:
            return
        target = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='схлопывание.xlsx', filetypes=[('Excel', '*.xlsx')])
        if not target:
            return
        button.config(state='disabled')
        status.set('Выполняется расчёт…')
        def finish(error, stats=None, bad=None):
            button.config(state='normal')
            if error:
                status.set('Расчёт не завершён.')
                messagebox.showerror('Ошибка', error)
            else:
                status.set(f"Готово. Освобождено тар: {stats['перемещено_тар']}")
                messagebox.showinfo('Готово', f"Отчёт: {target}\nТар для сверки: {bad}\nИсходно переполненных: {stats['тар_с_исходным_переполнением']}")
        def worker():
            try:
                stats, bad = run(source, target, q, d)
                root.after(0, lambda: finish(None, stats, bad))
            except Exception as exc:
                root.after(0, lambda error=str(exc): finish(error))
        threading.Thread(target=worker, daemon=True).start()
    button = ttk.Button(frame, text='Выбрать Excel и рассчитать', command=start)
    button.pack(pady=15)
    ttk.Label(frame, textvariable=status).pack(anchor='w')
    root.mainloop()


if __name__ == '__main__':
    main()
