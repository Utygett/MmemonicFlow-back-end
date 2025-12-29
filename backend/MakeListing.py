import os
from pathlib import Path


def create_listing(output_file="listing.txt"):
    """
    Создает файл listing.txt с содержимым файлов из папок app и tests
    Формат: имя файла, затем его содержимое
    """

    # Папки для обработки
    folders = ["tests"]

    # Папки и файлы для исключения
    exclude_dirs = {"__pycache__", ".git", ".idea", ".vscode", "node_modules", "venv", "env", ".pytest_cache"}
    exclude_extensions = {".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin", ".jpg", ".jpeg", ".png",
                          ".gif", ".pdf", ".zip", ".tar", ".gz", ".log", ".tmp", ".swp", ".DS_Store", ".sh"}

    # Открываем файл для записи
    with open(output_file, "w", encoding="utf-8") as out_file:

        for folder in folders:
            # Проверяем существование папки
            if not os.path.exists(folder):
                print(f"Предупреждение: Папка '{folder}' не найдена, пропускаем...")
                continue

            print(f"Обрабатываю папку: {folder}")

            # Рекурсивно ищем все файлы в папке и подпапках
            all_files = []
            for root, dirs, files in os.walk(folder):
                # Исключаем ненужные директории
                dirs[:] = [d for d in dirs if d not in exclude_dirs]

                for filename in files:
                    # Проверяем расширение файла
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in exclude_extensions:
                        continue

                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, ".")
                    all_files.append((relative_path, full_path))

            # Сортируем файлы по пути для порядка
            all_files.sort(key=lambda x: x[0])

            # Обрабатываем каждый файл
            for relative_path, full_path in all_files:
                try:
                    # Читаем содержимое файла
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Записываем имя файла
                    out_file.write(f"=== Файл: {relative_path} ===\n")

                    # Записываем содержимое
                    out_file.write(content)

                    # Добавляем разделитель между файлами
                    if not content.endswith('\n'):
                        out_file.write("\n")
                    out_file.write("=" * 50 + "\n\n")

                    print(f"  - Добавлен: {relative_path}")

                except UnicodeDecodeError:
                    # Пробуем другую кодировку
                    try:
                        with open(full_path, "r", encoding="cp1251", errors='ignore') as f:
                            content = f.read()

                        out_file.write(f"=== Файл: {relative_path} ===\n")
                        out_file.write(content)
                        if not content.endswith('\n'):
                            out_file.write("\n")
                        out_file.write("=" * 50 + "\n\n")
                        print(f"  - Добавлен (другая кодировка): {relative_path}")

                    except:
                        # Пропускаем бинарные файлы
                        print(f"  - Пропущен (бинарный файл): {relative_path}")

                except Exception as e:
                    print(f"  - Ошибка при чтении {relative_path}: {e}")
                    # В случае ошибки все равно записываем имя файла
                    out_file.write(f"=== Файл: {relative_path} ===\n")
                    out_file.write(f"[ОШИБКА ЧТЕНИЯ: {e}]\n")
                    out_file.write("=" * 50 + "\n\n")

    print(f"\nГотово! Результат сохранен в файл: {output_file}")


if __name__ == "__main__":
    create_listing()