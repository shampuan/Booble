#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import sqlite3
import os
import subprocess
from urllib.parse import unquote

# Terminaldeki font ve OpenType uyarılarını susturur
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db.debug=false"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QLineEdit, QWidget, QTextBrowser, QHBoxLayout, QProgressBar, 
                             QPushButton, QStackedWidget, QLabel, QToolBar)
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtCore import Qt, QSize

# Linux/Debian tabanlı sistemler için X11 zorlaması
os.environ["QT_QPA_PLATFORM"] = "xcb" # GNOME ortamında sıkıntısız açılması için. 

class BoobleApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Booble - Masaüstü Arama")
        self.setWindowIcon(QIcon(os.path.join(BASE_DIR, "boobleicon.png")))
        self.resize(1000, 750)
        
        # Geçmiş takibi
        self.history_stack = [0]
        
        # Ana yönetici
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Arayüz Bileşenleri
        self.create_nav_toolbar()
        self.create_menu_bar()

        # Sayfaları Kur
        self.setup_home_page()
        self.setup_results_page()

        # Örnek Veri
        self.init_database()
        

    def create_nav_toolbar(self):
        nav_bar = self.addToolBar("Navigasyon") # Toolbar'ı ana pencereye eklemeyi unutmamalıyız
        nav_bar.setMovable(False)
        from PyQt6.QtCore import QSize
        nav_bar.setIconSize(QSize(36, 36)) # İkonları 36x36 yaparak büyüttük

        from PyQt6.QtGui import QIcon

        back_act = QAction(QIcon(os.path.join(BASE_DIR, "go-previous.png")), "", self)
        back_act.setToolTip("Geri Dön")
        back_act.triggered.connect(self.go_back)
        nav_bar.addAction(back_act)
        
        nav_bar.addSeparator()
        
        refresh_act = QAction(QIcon(os.path.join(BASE_DIR, "media-playlist-repeat.png")), "", self)
        refresh_act.setToolTip("İndekslemeyi Yeniden Başlat")
        refresh_act.triggered.connect(self.start_indexing)
        nav_bar.addAction(refresh_act)
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # Dosya Menüsü
        file_menu = menubar.addMenu('&Dosya')
        
        index_action = QAction('İndekslemeyi Başlat', self)
        index_action.setShortcut("Ctrl+I")
        index_action.triggered.connect(self.start_indexing)
        file_menu.addAction(index_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Çıkış', self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Ayarlar Menüsü
        settings_menu = menubar.addMenu('&Ayarlar')
        options_action = QAction('Seçenekler...', self)
        options_action.triggered.connect(self.show_options_dialog)
        settings_menu.addAction(options_action)
        
        # Yardım Menüsü
        help_menu = menubar.addMenu('&Yardım')
        about_action = QAction('Hakkında', self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def init_database(self):
        # ~/.config/Booble/ yolunu oluştur
        config_path = os.path.expanduser("~/.config/Booble")
        if not os.path.exists(config_path):
            os.makedirs(config_path)
            
        db_path = os.path.join(config_path, "booble_index.db")
        self.settings_path = os.path.join(config_path, "settings.json")
        self.load_settings()
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        self.cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS files_index USING fts5(
                title, 
                path, 
                content, 
                tags
            )
        """)
        self.conn.commit()
        
    def load_settings(self):
        import json
        default_settings = {
            "scan_mode": "all",  # "all" veya "custom"
            "custom_path": "",
            "exclude_list": ["/proc", "/sys", "/dev", "/run", "/var/lib", "/var/cache", "/tmp"]
        }
        
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            except:
                self.settings = default_settings
        else:
            self.settings = default_settings
            self.save_settings()

    def save_settings(self):
        import json
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Ayarlar kaydedilemedi: {e}")
        
    def index_files(self, folder_path):
        self.status_container.show()
        self.current_path_label.setText("Hazırlanıyor...")
        QApplication.processEvents()
        
        exclude_dirs = set(self.settings.get("exclude_list", []))
        all_items = []
        
        # Hızlı tarama ve listeleme
        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if os.path.join(root, d) not in exclude_dirs]
            for d in dirs:
                all_items.append((d, os.path.join(root, d), ""))
            for f in files:
                all_items.append((f, os.path.join(root, f), ""))
        
        total = len(all_items)
        self.pbar.setMaximum(total)
        self.cursor.execute("DELETE FROM files_index")
        
        for i, (name, path, content) in enumerate(all_items):
            try:
                self.cursor.execute(
                    "INSERT INTO files_index (title, path, content) VALUES (?, ?, ?)",
                    (name, path, content)
                )
                
                # Her 25 dosyada bir görsel güncelleme (Hız için)
                if i % 25 == 0 or i == total - 1:
                    self.pbar.setValue(i + 1)
                    # Yol çok uzunsa pencereyi itmemesi için kırp (Örn: 70 karakter)
                    # Sadece görsel olarak yolu bas, pencereyi zorlamaması için metni kırp
                    self.pbar.setValue(i + 1)
                    display_path = (path[:60] + '...') if len(path) > 60 else path
                    self.current_path_label.setText(display_path)
                    QApplication.processEvents()
                    
            except:
                continue

        self.conn.commit()
        self.status_container.hide()

    def setup_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        
        layout.addStretch(2)

        # GIMP ile hazırladığın özgür logo
        logo_label = QLabel()
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(os.path.join(BASE_DIR, "Booble_logo.png"))
        
        # Logoyu pencereye göre ölçeklendir (Orantılı şekilde)
        logo_label.setPixmap(pixmap.scaled(443, 104, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)
        
        # Slogan (Özgür font ile)
        slogan = QLabel("Bilgisayarında Boob'la!")
        slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slogan.setFont(QFont("DejaVu Sans", 14)) # Özgür font kullanımı
        slogan.setStyleSheet("color: #70757a;")
        layout.addWidget(slogan)

        # Arama Çubuğu
        self.home_search = QLineEdit()
        self.home_search.setPlaceholderText("Booble'da ara...")
        self.home_search.setFixedWidth(550)
        self.home_search.setMinimumHeight(50)
        self.home_search.setFont(QFont("DejaVu Sans", 12))
        self.home_search.returnPressed.connect(self.initiate_search)
        
        from PyQt6.QtGui import QIcon

        search_btn = QPushButton()
        search_btn.setIcon(QIcon(os.path.join(BASE_DIR, "page-zoom.png")))
        search_btn.setIconSize(QSize(40, 40)) # İkonu iyice büyüttük
        search_btn.setFixedSize(70, 50) # Buton genişliğini artırdık, yüksekliği arama çubuğuyla eşitledik
        search_btn.clicked.connect(self.initiate_search)

        h_search_layout = QHBoxLayout()
        h_search_layout.addStretch()
        h_search_layout.addWidget(self.home_search)
        h_search_layout.setSpacing(10) # Arama çubuğu ile buton arasına biraz boşluk
        h_search_layout.addWidget(search_btn)
        h_search_layout.addStretch()
        layout.addLayout(h_search_layout)

        # İndeksleme Durum Alanı
        # En alta yapışık, sade durum şeridi
        self.status_container = QWidget()
        self.status_container.hide()
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(20, 10, 20, 10) # Kenarlardan daha dengeli boşluk
        
        self.status_label = QLabel("Taranıyor:")
        status_layout.addWidget(self.status_label)
        
        self.pbar = QProgressBar()
        self.pbar.setMinimumHeight(20) # Daha yüksek
        self.pbar.setMinimumWidth(300) # Daha uzun
        status_layout.addWidget(self.pbar)
        
        self.current_path_label = QLabel("")
        status_layout.addWidget(self.current_path_label, 1) # Yolu sağa doğru uzatır
        
        layout.addStretch(3)
        layout.addWidget(self.status_container)
        self.stack.addWidget(page)
        

    def setup_results_page(self):
        page = QWidget()
        from PyQt6.QtGui import QPixmap
        layout = QVBoxLayout(page)

        top_bar = QHBoxLayout()
        
        # Sonuçlar sayfası logosu
        res_logo = QLabel()
        res_pixmap = QPixmap(os.path.join(BASE_DIR, "Booble_logo.png"))
        res_logo.setPixmap(res_pixmap.scaled(85, 85, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        top_bar.addWidget(res_logo)

        self.res_search = QLineEdit()
        self.res_search.setMinimumHeight(35)
        self.res_search.setFont(QFont("sans-serif", 11))
        self.res_search.returnPressed.connect(self.update_search)
        top_bar.addWidget(self.res_search)
        layout.addLayout(top_bar)

        self.results_area = QTextBrowser()
        self.results_area.setOpenLinks(False)  # Kendi fonksiyonumuzun çalışması için bunu kapatmalıyız
        self.results_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_area.anchorClicked.connect(self.open_file)
        self.results_area.customContextMenuRequested.connect(self.show_context_menu)
        self.results_area.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.results_area)
        
        self.stack.addWidget(page)


    def go_back(self):
        if len(self.history_stack) > 1:
            self.history_stack.pop()
            self.stack.setCurrentIndex(self.history_stack[-1])

    def initiate_search(self):
        query = self.home_search.text()
        if query:
            self.res_search.setText(query)
            self.update_search()
            self.stack.setCurrentIndex(1)
            self.history_stack.append(1)

    def update_search(self):
        q = self.res_search.text()
        if not q:
            return
            
        # SQLite FTS5 ile hem başlıkta hem yolda hem içerikte ara
        query = "SELECT title, path, content FROM files_index WHERE files_index MATCH ?"
        self.cursor.execute(query, (f'title:"{q}"*',))
        results = self.cursor.fetchall()
        
        # Sonuçları yeni formata uygun şekilde işle
        formatted_results = []
        for r in results:
            # İçerik tarama kapalı olduğu için açıklama boş bırakılır
            description = ""
            
            formatted_results.append({
                'title': r[0],
                'path': r[1],
                'desc': description
            })
            
        self.display_results(formatted_results)
        
    def display_results(self, results):
        # Sistem renklerini alalım
        palette = self.palette()
        text_color = palette.color(palette.ColorGroup.Active, palette.ColorRole.WindowText).name()
        link_color = palette.color(palette.ColorGroup.Active, palette.ColorRole.Link).name()
        sub_text_color = palette.color(palette.ColorGroup.Active, palette.ColorRole.PlaceholderText).name()

        html = f"<div style='font-family: sans-serif; line-height: 1.6; padding: 10px; color: {text_color};'>"
        
        if not results:
            html += "<h2>Sonuç bulunamadı.</h2>"
        else:
            for r in results:
                is_dir = os.path.isdir(r['path'])
                # İçerik özeti varsa göster, yoksa o alanı boş geç
                desc_html = f"<div style='color: #4d5156; font-size: 10.5pt; line-height: 1.4;'>{r['desc']}</div>" if r['desc'] else ""
                
                # HTML bloğunu birleştiriyoruz (Google Tarzı: Başlık -> Yol -> Açıklama)
                html += f"""
                <div style='margin-bottom: 22px;'>
                    <div style='margin-bottom: 2px;'>
                        <a href="{r['path']}" style="color: {link_color}; font-size: 14pt; text-decoration: none; font-weight: normal;">{"📁 " if is_dir else ""}{r['title']}</a>
                    </div>
                    <div style='color: #006621; font-size: 10pt; margin-bottom: 4px;'>{r['path']}</div>
                    {desc_html}
                </div>
                """
        
        html += "</div>"
        self.results_area.setHtml(html)

    def open_file(self, url):
        # En güvenli yöntem: QUrl'nin kendi yerel dosya dönüştürücüsünü kullan, 
        # eğer başarısız olursa manuel temizlik yap.
        file_path = url.toLocalFile()
        
        if not file_path:
            raw_path = url.toString()
            if raw_path.startswith("file://"):
                file_path = unquote(raw_path[7:])
            else:
                file_path = unquote(raw_path)

        # Linux sistemlerde yol mutlaka '/' ile başlamalıdır
        if sys.platform == 'linux' and not file_path.startswith('/'):
            file_path = '/' + file_path

        if os.path.exists(file_path):
            try:
                if sys.platform == 'linux':
                    # os.system yerine subprocess.Popen kullanarak uygulamanın kilitlenmesini önlüyoruz
                    subprocess.Popen(['xdg-open', file_path])
                elif sys.platform == 'win32':
                    os.startfile(file_path)
                else:
                    subprocess.Popen(['open', file_path])
            except Exception as e:
                print(f"Dosya açılamadı: {e}")
                
    def start_indexing(self):
        # Burada şimdilik sabit bir klasör veriyoruz, 
        # ileride bunu ayarlardan seçilebilir yaparız.
        if self.settings.get("scan_mode") == "custom" and self.settings.get("custom_path"):
            target_folder = self.settings.get("custom_path")
        else:
            target_folder = "/"
        self.index_files(target_folder)
        
        # İşlem bitince kullanıcıya bilgi verelim
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Booble", "İndeksleme başarıyla tamamlandı!")

    def show_context_menu(self, pos):
        anchor = self.results_area.anchorAt(pos)
        if not anchor:
            return

        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        
        open_act = QAction("Aç", self)
        open_act.triggered.connect(lambda: self.open_file(anchor))
        menu.addAction(open_act)

        open_folder_act = QAction("Bulunduğu Klasörü Aç", self)
        open_folder_act.triggered.connect(lambda: self.open_folder(anchor))
        menu.addAction(open_folder_act)

        menu.exec(self.results_area.mapToGlobal(pos))

    def open_folder(self, path_input):
        # path_input bir QUrl veya string olabilir, temizleyelim
        if hasattr(path_input, 'toLocalFile'):
            file_path = path_input.toLocalFile()
        else:
            file_path = str(path_input)

        if not file_path or not os.path.exists(file_path):
            return

        # Dosya ise klasörünü al, klasör ise kendisini kullan
        folder_path = os.path.dirname(file_path) if os.path.isfile(file_path) else file_path

        try:
            if sys.platform == 'linux':
                subprocess.Popen(['xdg-open', folder_path])
            elif sys.platform == 'win32':
                subprocess.Popen(['explorer', os.path.normpath(folder_path)])
            else:
                subprocess.Popen(['open', folder_path])
        except Exception as e:
            print(f"Klasör açılamadı: {e}")

    def show_about_dialog(self):
        from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Booble Hakkında")
        dialog.setFixedSize(450, 400)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        layout = QVBoxLayout(dialog)

        content = f"""
        <div style='font-family: DejaVu Sans, sans-serif;'>
            <h2 style='color: #4285f4; margin-bottom: 0;'>Booble Hakkında</h2>
            <hr>
            <p><b>Sürüm:</b> 1.0.0<br>
            <b>Lisans:</b> GNU GPLv3<br>
            <b>Programlama Dili:</b> Python3<br>
            <b>GUI/UX:</b> PyQt6<br>
            <b>Geliştirici:</b> A. Serhat KILIÇOĞLU (shampuan)<br>
            <b>Github:</b> <a href="https://www.github.com/shampuan" style="color: #1a0dab;">www.github.com/shampuan</a></p>
            
            <p style='line-height: 1.4;'>Bu program, bilinen arama motoruna benzer arayüzüyle, bilgisayarınızda daha iyi arama yapmanızı sağlayan etkili bir yerel arama motorudur.</p>
            
            <p><i>Bu program hiçbir garanti getirmez.</i></p>
            
            <p style='font-size: 10pt; color: #70757a;'>Telif hakkı (C) 2026 - A. Serhat KILIÇOĞLU</p>
        </div>
        """
        
        label = QLabel(content)
        label.setOpenExternalLinks(True) # Linkin tarayıcıda açılmasını sağlar
        label.setWordWrap(True)
        layout.addWidget(label)
        
        btn_close = QPushButton("Tamam")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)
        
        dialog.exec()

    def show_options_dialog(self):
        from PyQt6.QtWidgets import QDialog, QRadioButton, QFileDialog, QListWidget, QGroupBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Booble Seçenekler")
        dialog.setFixedWidth(400)
        d_layout = QVBoxLayout(dialog)

        # Tarama Kapsamı Grubu
        group_box = QGroupBox("Tarama Kapsamı")
        group_layout = QVBoxLayout()
        
        self.radio_all = QRadioButton("Tüm Sistem (/)")
        self.radio_custom = QRadioButton("Özel Klasör")
        
        # Mevcut ayarı yükle
        if self.settings.get("scan_mode") == "custom":
            self.radio_custom.setChecked(True)
        else:
            self.radio_all.setChecked(True)
            
        group_layout.addWidget(self.radio_all)
        group_layout.addWidget(self.radio_custom)
        
        # Özel Yol Seçme Alanı
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(self.settings.get("custom_path", ""))
        self.path_edit.setReadOnly(True)
        btn_browse = QPushButton("Gözat...")
        
        def browse_folder():
            folder = QFileDialog.getExistingDirectory(dialog, "Tarama Klasörü Seç")
            if folder:
                self.path_edit.setText(folder)
        
        btn_browse.clicked.connect(browse_folder)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(btn_browse)
        group_layout.addLayout(path_layout)
        group_box.setLayout(group_layout)
        d_layout.addWidget(group_box)

        # Hariç Listesi Başlığı ve Butonları
        exclude_label_layout = QHBoxLayout()
        exclude_label_layout.addWidget(QLabel("Hariç Tutulan Yollar:"))
        
        btn_add_exclude = QPushButton("+")
        btn_add_exclude.setFixedWidth(30)
        btn_remove_exclude = QPushButton("-")
        btn_remove_exclude.setFixedWidth(30)
        
        exclude_label_layout.addStretch()
        exclude_label_layout.addWidget(btn_add_exclude)
        exclude_label_layout.addWidget(btn_remove_exclude)
        d_layout.addLayout(exclude_label_layout)

        self.exclude_list_widget = QListWidget()
        self.exclude_list_widget.addItems(self.settings.get("exclude_list", []))
        d_layout.addWidget(self.exclude_list_widget)

        # Ekleme ve Çıkarma Fonksiyonları
        def add_exclude_path():
            folder = QFileDialog.getExistingDirectory(dialog, "Hariç Tutulacak Klasörü Seç")
            if folder and folder not in [self.exclude_list_widget.item(i).text() for i in range(self.exclude_list_widget.count())]:
                self.exclude_list_widget.addItem(folder)

        def remove_exclude_path():
            current_item = self.exclude_list_widget.currentItem()
            if current_item:
                self.exclude_list_widget.takeItem(self.exclude_list_widget.row(current_item))

        btn_add_exclude.clicked.connect(add_exclude_path)
        btn_remove_exclude.clicked.connect(remove_exclude_path)

        # Kaydet Butonu
        btn_save = QPushButton("Ayarları Kaydet")
        def save_and_close():
            self.settings["scan_mode"] = "custom" if self.radio_custom.isChecked() else "all"
            self.settings["custom_path"] = self.path_edit.text()
            self.settings["exclude_list"] = [self.exclude_list_widget.item(i).text() for i in range(self.exclude_list_widget.count())]
            self.save_settings()
            dialog.accept()
            
        btn_save.clicked.connect(save_and_close)
        d_layout.addWidget(btn_save)
        
        dialog.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BoobleApp()
    window.show()
    sys.exit(app.exec())
