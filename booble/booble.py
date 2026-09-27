#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import sqlite3
import os
import subprocess
import html
import gettext
from urllib.parse import unquote

# Terminaldeki font ve OpenType uyarılarını susturur
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db.debug=false"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from PyQt6.QtCore import QLocale

# Çeviri dizinleri (Önce proje içi 'locale', yoksa sistem /usr/share/locale)
LOCALE_DIR = os.path.join(BASE_DIR, "locale")
if not os.path.exists(LOCALE_DIR):
    LOCALE_DIR = "/usr/share/locale"

import builtins

def get_language_name(code):
    """Herhangi bir dil kodunu kendi anadilindeki isme dönüştürür (Sınırsızdır)."""
    if code == "en":
        return "English"
    try:
        loc = QLocale(code)
        native = loc.nativeLanguageName()
        if native:
            # Varsa parantez veya lehçe eklerini temizle (Örn: "Deutsch (Deutschland)" -> "Deutsch")
            clean_name = native.split("(")[0].strip()
            return clean_name.capitalize()
    except Exception:
        pass
    return code

def get_available_languages():
    """locale klasörünü tamamen dinamik tarar; hangi dil eklenirse menüde gösterir."""
    # Varsayılan dil her zaman İngilizcedir (kodun taban dili)
    languages = {"en": "English (Default)"}
    
    if os.path.exists(LOCALE_DIR):
        try:
            for entry in os.scandir(LOCALE_DIR):
                if entry.is_dir():
                    mo_file = os.path.join(entry.path, "LC_MESSAGES", "booble.mo")
                    if os.path.exists(mo_file):
                        code = entry.name
                        if code != "en":
                            languages[code] = get_language_name(code)
        except Exception as e:
            print(f"Dil tarama hatası: {e}")

    return languages

def setup_translation(lang_code="en"):
    """Seçilen dile göre gettext çevirisini bağlar."""
    global _
    # Kodun taban dili İngilizce olduğundan, 'en' seçiliyse doğrudan kod metinleri basılır
    if lang_code == "en":
        builtins._ = lambda s: s
        _ = lambda s: s
        return

    try:
        t = gettext.translation("booble", localedir=LOCALE_DIR, languages=[lang_code], fallback=True)
        t.install()
        _ = t.gettext
        print(f"[Booble] Dil aktif edildi: {lang_code}")
    except Exception as e:
        print(f"[Booble] Dil dosyası bulunamadı ({lang_code}): {e}")
        builtins._ = lambda s: s
        _ = lambda s: s

# Başlangıçta İngilizce (doğal kod)
builtins._ = lambda s: s
_ = lambda s: s


import math
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QLineEdit, QWidget, QTextBrowser, QHBoxLayout, QProgressBar, 
                             QPushButton, QStackedWidget, QLabel, QToolBar, QMessageBox,
                             QRadioButton, QButtonGroup, QMenu, QDialog, QFileDialog,
                             QListWidget, QGroupBox)
import json
from PyQt6.QtGui import QAction, QActionGroup, QFont, QIcon, QPixmap, QImageReader, QMouseEvent
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QFileInfo, QMimeDatabase, QTimer, QUrl

# Kullanıcının görmeyeceği, daimi olarak kilitli arka plan sistem klasörleri
SYSTEM_EXCLUDES = {
    "/proc", "/sys", "/dev", "/run", "/tmp", "/var/tmp",
    "/var/lib", "/var/cache", "/var/lib/docker", "/var/lib/flatpak",
    "/snap", "/lost+found"
}

THUMB_CACHE_DIR = os.path.expanduser("~/.cache/Booble/thumbs")
os.makedirs(THUMB_CACHE_DIR, exist_ok=True)

def human_readable_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"

import hashlib
import urllib.parse

def get_freedesktop_thumbnail(file_path):
    """Linux'un (GNOME/Dolphin/XFCE) hazırda tuttuğu video/resim önizlemelerini çeker."""
    try:
        uri = "file://" + urllib.parse.quote(os.path.abspath(file_path))
        md5_hash = hashlib.md5(uri.encode('utf-8')).hexdigest()
        for base in ["~/.cache/thumbnails/large", "~/.cache/thumbnails/normal"]:
            t_path = os.path.expanduser(f"{base}/{md5_hash}.png")
            if os.path.exists(t_path):
                return t_path
    except:
        pass
    return None

def get_thumbnail_path(file_path):
    """Resim ve videolar için 16:9 geniş (140x90) önizleme üretir veya sistemden çeker."""
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.svg'}
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.webm', '.mov', '.flv', '.wmv', '.m4v'}
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
        return None, None

    media_type = "video" if ext in VIDEO_EXTS else "image"

    # 1. Adım: Linux sistem önbelleğinde (Nautilus/Dolphin) zaten var mı?
    fd_thumb = get_freedesktop_thumbnail(file_path)
    if fd_thumb:
        return fd_thumb, media_type

    # 2. Adım: Booble'ın kendi önbelleğinde var mı?
    file_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    thumb_file = os.path.join(THUMB_CACHE_DIR, f"{file_hash}.png")
    if os.path.exists(thumb_file):
        return thumb_file, media_type

    # 3. Adım: Yoksa hızlıca üret
    try:
        if ext in IMAGE_EXTS:
            reader = QImageReader(file_path)
            reader.setAutoTransform(True)
            if reader.size().isValid():
                reader.setScaledSize(QSize(140, 95))
                img = reader.read()
                if not img.isNull():
                    img.save(thumb_file, "PNG")
                    return thumb_file, media_type
        elif ext in VIDEO_EXTS:
            # ffmpeg veya ffmpegthumbnailer ile videonun 3. saniyesinden hafif kare al
            cmd = ['ffmpegthumbnailer', '-i', file_path, '-o', thumb_file, '-s', '140']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.5)
            if res.returncode == 0 and os.path.exists(thumb_file):
                return thumb_file, media_type
            else:
                # Yedek: Standart ffmpeg komutu
                cmd_ffmpeg = ['ffmpeg', '-y', '-ss', '00:00:03', '-i', file_path, '-vframes', '1', '-vf', 'scale=140:90', thumb_file]
                res_f = subprocess.run(cmd_ffmpeg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
                if res_f.returncode == 0 and os.path.exists(thumb_file):
                    return thumb_file, media_type
    except:
        pass

    return None, media_type

ICON_CACHE_DIR = os.path.expanduser("~/.cache/Booble/icons")
os.makedirs(ICON_CACHE_DIR, exist_ok=True)

class ClickableLogo(QLabel):
    """Ana sayfaya dönmeyi sağlayan, fare üzerine gelince hafifçe parlayan logo."""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QLabel {
                padding: 2px;
                border-radius: 6px;
            }
            QLabel:hover {
                background-color: rgba(66, 133, 244, 0.12);
            }
        """)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

def get_media_metadata(file_path, media_type):
    """Görseller ve videolar için İngilizce meta veriler (çözünürlük, codec, süre) döndürür."""
    meta = []
    ext = os.path.splitext(file_path)[1].lower().replace('.', '').upper()
    
    if media_type == "image":
        meta.append(f"Format: {ext}")
        try:
            reader = QImageReader(file_path)
            sz = reader.size()
            if sz.isValid():
                meta.append(f"{sz.width()}x{sz.height()}")
        except:
            pass
    elif media_type == "video":
        meta.append(f"Format: {ext}")
        try:
            # ffprobe ile video süre, çözünürlük ve codec bilgisini JSON olarak çek
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.0)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                
                # Süre hesabı
                duration_sec = float(data.get('format', {}).get('duration', 0))
                if duration_sec > 0:
                    mins = int(duration_sec // 60)
                    secs = int(duration_sec % 60)
                    meta.append(f"Duration: {mins:02d}:{secs:02d}")

                # Çözünürlük ve Video Kodek
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        codec = stream.get('codec_name', '').upper()
                        if codec:
                            meta.append(f"Codec: {codec}")
                        w = stream.get('width')
                        h = stream.get('height')
                        if w and h:
                            meta.append(f"{w}x{h}")
                        break
        except:
            pass

    return meta

def get_system_theme_icon_path(is_dir, file_path=""):
    """Sistemin seçili temasından (Papirus/Adwaita/Breeze) güvenli PNG ikonu çeker."""
    if is_dir:
        theme_names = ["folder", "inode-directory"]
        cache_name = "sys_folder.png"
    else:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in {'.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar'}:
            theme_names = ["package-x-generic", "application-zip"]
            cache_name = "sys_archive.png"
        elif ext in {'.mp3', '.ogg', '.flac', '.wav', '.m4a'}:
            theme_names = ["audio-x-generic", "audio-headphones"]
            cache_name = "sys_audio.png"
        elif ext in {'.mp4', '.mkv', '.avi', '.webm', '.mov'}:
            theme_names = ["video-x-generic", "video"]
            cache_name = "sys_video.png"
        elif ext in {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.svg', '.ico', '.tiff'}:
            theme_names = ["image-x-generic", "image"]
            cache_name = "sys_image.png"
        elif ext in {'.pdf'}:
            theme_names = ["application-pdf", "x-office-document"]
            cache_name = "sys_pdf.png"
        elif ext in {'.py', '.sh', '.c', '.cpp', '.js', '.html', '.css'}:
            theme_names = ["text-x-script", "text-x-generic"]
            cache_name = "sys_code.png"
        elif ext in {'.deb', '.rpm'}:
            theme_names = ["package-x-generic"]
            cache_name = "sys_package.png"
        else:
            theme_names = ["text-x-generic", "unknown"]
            cache_name = "sys_file.png"

    cached_icon_path = os.path.join(ICON_CACHE_DIR, cache_name)
    if os.path.exists(cached_icon_path):
        return cached_icon_path

    # Sistem temasından ikonu çek ve diske PNG olarak yaz
    for name in theme_names:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            pixmap = icon.pixmap(22, 22)
            if not pixmap.isNull():
                pixmap.save(cached_icon_path, "PNG")
                return cached_icon_path

    return None

class IndexWorker(QThread):
    progress = pyqtSignal(int, str)       # (taranan dosya sayısı, anlık yol)
    finished = pyqtSignal(int)            # (toplam indekslenen dosya sayısı)

    def __init__(self, db_path, target_folder, user_excludes):
        super().__init__()
        self.db_path = db_path
        self.target_folder = os.path.abspath(target_folder)
        
        # Sabit sistem klasörleri + Kullanıcının eklediği özel yollar birleştirilir
        clean_user_excludes = {os.path.abspath(p) for p in user_excludes if p.strip()}
        self.all_excludes = SYSTEM_EXCLUDES.union(clean_user_excludes)
        
        # Çakışma önlemi: Taranacak hedef klasörün kendisi hariç tutulamaz
        self.all_excludes.discard(self.target_folder)
        
        self.skip_names = {".git", ".cache", "node_modules", "__pycache__"}

    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # SQLite maksimum hız ayarları
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA journal_mode = MEMORY")
        cursor.execute("PRAGMA cache_size = -64000")  # ~64 MB RAM önbellek
        cursor.execute("PRAGMA temp_store = MEMORY")

        # Tabloyu Türkçe karakter korumalı (remove_diacritics 0) olarak sıfırdan kur
        cursor.execute("DROP TABLE IF EXISTS files_index")
        cursor.execute("""
            CREATE VIRTUAL TABLE files_index USING fts5(
                title, 
                path, 
                content, 
                tags,
                tokenize = 'unicode61 remove_diacritics 0'
            )
        """)
        conn.commit()

        batch = []
        BATCH_SIZE = 5000
        count = 0

        def scan_dir(path):
            nonlocal count, batch
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        # İsim bazlı filtreleme
                        if entry.name in self.skip_names:
                            continue

                        full_path = entry.path

                        # Hariç tutulan yol kontrolü (Sistem + Kullanıcı)
                        if entry.is_dir(follow_symlinks=False):
                            abs_path = os.path.abspath(full_path)
                            if abs_path in self.all_excludes:
                                continue
                            batch.append((entry.name, full_path, ""))
                            count += 1
                            if count % 200 == 0:
                                self.progress.emit(count, full_path)
                            scan_dir(full_path)
                        else:
                            batch.append((entry.name, full_path, ""))
                            count += 1
                            if count % 200 == 0:
                                self.progress.emit(count, full_path)

                        # Toplu diske yazma (Batching)
                        if len(batch) >= BATCH_SIZE:
                            cursor.executemany(
                                "INSERT INTO files_index (title, path, content) VALUES (?, ?, ?)",
                                batch
                            )
                            conn.commit()
                            batch.clear()
            except (PermissionError, FileNotFoundError, OSError):
                pass

        scan_dir(self.target_folder)

        # Kalan son paketi kaydet
        if batch:
            cursor.executemany(
                "INSERT INTO files_index (title, path, content) VALUES (?, ?, ?)",
                batch
            )
            conn.commit()
            batch.clear()

        conn.close()
        self.finished.emit(count)


FILTER_EXTS = {
    "docs": ['.pdf', '.doc', '.docx', '.odt', '.txt', '.rtf', '.xls', '.xlsx', '.ods', '.ppt', '.pptx', '.odp', '.csv', '.md'],
    "images": ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.svg', '.ico', '.tiff'],
    "videos": ['.mp4', '.mkv', '.avi', '.webm', '.mov', '.flv', '.wmv', '.m4v'],
    "audio": ['.mp3', '.ogg', '.flac', '.wav', '.m4a', '.aac', '.wma']
}

class SearchWorker(QThread):
    results_ready = pyqtSignal(list, int, int)  # (rows, total_results, current_page)

    def __init__(self, db_path, query, page, page_size, filter_type="all"):
        super().__init__()
        self.db_path = db_path
        self.query = query
        self.page = page
        self.page_size = page_size
        self.filter_type = filter_type

    def run(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        raw_query = self.query.strip()
        offset = (self.page - 1) * self.page_size
        rows = []
        total_results = 0

        # Uzantı filtresi SQL şartı hazırlığı
        ext_clause = ""
        ext_params = []
        if self.filter_type in FILTER_EXTS:
            ext_list = FILTER_EXTS[self.filter_type]
            ext_clause = " AND (" + " OR ".join(["title LIKE ?" for _ in ext_list]) + ")"
            ext_params = [f"%{ext}" for ext in ext_list]

        try:
            # 1. Joker karakter (*) araması
            if '*' in raw_query or '?' in raw_query:
                like_pattern = raw_query.replace('*', '%').replace('?', '_')
                base_sql = f"WHERE title LIKE ?{ext_clause}"
                params = [like_pattern] + ext_params

                cursor.execute(f"SELECT count(*) FROM files_index {base_sql}", params)
                total_results = cursor.fetchone()[0]

                cursor.execute(f"SELECT title, path FROM files_index {base_sql} LIMIT ? OFFSET ?",
                               params + [self.page_size, offset])
                rows = cursor.fetchall()

            # 2. Gizli dosya (.) araması
            elif raw_query.startswith('.'):
                like_pattern = f"{raw_query}%"
                base_sql = f"WHERE title LIKE ?{ext_clause}"
                params = [like_pattern] + ext_params

                cursor.execute(f"SELECT count(*) FROM files_index {base_sql}", params)
                total_results = cursor.fetchone()[0]

                cursor.execute(f"SELECT title, path FROM files_index {base_sql} LIMIT ? OFFSET ?",
                               params + [self.page_size, offset])
                rows = cursor.fetchall()

            # 3. Normal FTS5 araması (Tırnak ve sözdizimi korumalı)
            else:
                # FTS5 özel anahtar kelimeleri ve tırnak işaretlerini etkisizleştir
                safe_q = raw_query.replace('"', '""').strip()
                # Boş tırnak kalmışsa arama yapma
                if not safe_q.replace('"', ''):
                    safe_q = ""

                if safe_q:
                    fts_match = f'"{safe_q}"*'
                    base_sql = f"WHERE files_index MATCH ?{ext_clause}"
                    params = [f'title:{fts_match}'] + ext_params

                    cursor.execute(f"SELECT count(*) FROM files_index {base_sql}", params)
                    total_results = cursor.fetchone()[0]

                    cursor.execute(f"SELECT title, path FROM files_index {base_sql} LIMIT ? OFFSET ?",
                                   params + [self.page_size, offset])
                    rows = cursor.fetchall()
                else:
                    total_results = 0
                    rows = []

        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            total_results = 0
            rows = []

        conn.close()
        self.results_ready.emit(rows, total_results, self.page)

# Linux/Debian tabanlı sistemler için X11 zorlaması
os.environ["QT_QPA_PLATFORM"] = "xcb" # GNOME ortamında sıkıntısız açılması için. 

        


class BoobleApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_("Booble - Desktop Search"))
        self.setWindowIcon(QIcon(os.path.join(BASE_DIR, "boobleicon.png")))
        self.resize(1000, 750)
        
        # Geçmiş, Sayfalama ve Filtre Takibi
        self.history_stack = [0]
        self.current_page = 1
        self.page_size = 20
        self.total_results = 0
        self.current_query = ""
        self.current_filter = "all"
        self.mime_db = QMimeDatabase()
        
        # Ana yönetici
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Önce ayarları ve veritabanını yükle (Dilin arayüzden önce yüklenmesi için)
        self.init_database()

        # Arayüz Bileşenleri
        self.create_nav_toolbar()
        self.create_menu_bar()

        # Sayfaları Kur
        self.setup_home_page()
        self.setup_results_page()
        

    def create_nav_toolbar(self):
        nav_bar = self.addToolBar(_("Navigation"))
        nav_bar.setMovable(False)
        nav_bar.setIconSize(QSize(22, 22))
        nav_bar.setStyleSheet("""
            QToolBar {
                background: transparent;
                border: none;
                spacing: 6px;
                padding: 4px 10px;
            }
            QToolButton {
                background: transparent;
                border-radius: 6px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: rgba(128, 128, 128, 0.15);
            }
            QToolButton:pressed {
                background-color: rgba(128, 128, 128, 0.25);
            }
        """)

        back_act = QAction(QIcon(os.path.join(BASE_DIR, "go-previous.png")), "", self)
        back_act.setToolTip(_("Back"))
        back_act.triggered.connect(self.go_back)
        nav_bar.addAction(back_act)
        
        nav_bar.addSeparator()
        
        refresh_act = QAction(QIcon(os.path.join(BASE_DIR, "media-playlist-repeat.png")), "", self)
        refresh_act.setToolTip(_("Rebuild Index"))
        refresh_act.triggered.connect(self.start_indexing)
        nav_bar.addAction(refresh_act)
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # Dosya Menüsü
        file_menu = menubar.addMenu(_("&File"))
        
        index_action = QAction(_("Start Indexing"), self)
        index_action.setShortcut("Ctrl+I")
        index_action.triggered.connect(self.start_indexing)
        file_menu.addAction(index_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction(_("Exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Ayarlar Menüsü
        settings_menu = menubar.addMenu(_("&Settings"))
        options_action = QAction(_("Options..."), self)
        options_action.triggered.connect(self.show_options_dialog)
        settings_menu.addAction(options_action)
        
        # Yardım Menüsü
        help_menu = menubar.addMenu(_("&Help"))

        # Dinamik Dil Seçim Menüsü
        lang_menu = help_menu.addMenu(_("&Dil / Language"))
        lang_action_group = QActionGroup(self)
        lang_action_group.setExclusive(True)

        current_lang = self.settings.get("language", "en")
        available_langs = get_available_languages()

        for code, name in available_langs.items():
            act = QAction(name, self, checkable=True)
            act.setData(code)
            if code == current_lang:
                act.setChecked(True)
            act.triggered.connect(lambda checked, lang_code=code: self.change_language(lang_code))
            lang_action_group.addAction(act)
            lang_menu.addAction(act)

        help_menu.addSeparator()

        about_action = QAction(_("About"), self)
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
                tags,
                tokenize = 'unicode61 remove_diacritics 0'
            )
        """)
        self.conn.commit()
        
    def load_settings(self):
        import json
        default_settings = {
            "scan_mode": "all",
            "custom_path": "",
            "user_excludes": [],
            "language": "en"  # Varsayılan dil: İngilizce
        }
        
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                    if "user_excludes" not in self.settings:
                        old_list = self.settings.get("exclude_list", [])
                        self.settings["user_excludes"] = [
                            p for p in old_list if p not in SYSTEM_EXCLUDES
                        ]
                    if "language" not in self.settings:
                        self.settings["language"] = "en"
            except:
                self.settings = default_settings
        else:
            self.settings = default_settings
            self.save_settings()

        # Kayıtlı dili aktif et
        setup_translation(self.settings.get("language", "en"))

    def save_settings(self):
        import json
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Ayarlar kaydedilemedi: {e}")
        
    def on_index_progress(self, count, current_path):
        display_path = (current_path[:55] + '...') if len(current_path) > 55 else current_path
        self.current_path_label.setText(f"[{count:,}] {display_path}")

    def on_index_finished(self, total_count):
        self.pbar.setRange(0, 100)
        self.pbar.setValue(100)
        self.status_container.hide()
        msg = _("Total {count} files and folders indexed successfully.").format(count=f"{total_count:,}")
        QMessageBox.information(
            self, 
            _("Indexing Completed"), 
            msg
        )

    def setup_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        
        layout.addStretch(2)

        # GIMP ile hazırladığın özgür logo
        logo_label = QLabel()
        
        pixmap = QPixmap(os.path.join(BASE_DIR, "Booble_logo.png"))
        
        # Logoyu pencereye göre ölçeklendir (Orantılı şekilde)
        logo_label.setPixmap(pixmap.scaled(443, 104, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)
        
        # Slogan
        slogan = QLabel(_("Boob it on your computer!"))
        slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slogan.setFont(QFont("DejaVu Sans", 14))
        slogan.setStyleSheet("color: #70757a;")
        layout.addWidget(slogan)

        # Arama Çubuğu
        self.home_search = QLineEdit()
        self.home_search.setPlaceholderText(_("Search in Booble..."))
        self.home_search.setFixedWidth(550)
        self.home_search.setMinimumHeight(50)
        self.home_search.setFont(QFont("DejaVu Sans", 12))
        self.home_search.returnPressed.connect(self.initiate_search)

        search_btn = QPushButton()
        search_btn.setIcon(QIcon(os.path.join(BASE_DIR, "page-zoom.png")))
        search_btn.setIconSize(QSize(40, 40))
        search_btn.setFixedSize(70, 50)
        search_btn.setToolTip(_("Search"))
        search_btn.clicked.connect(self.initiate_search)

        h_search_layout = QHBoxLayout()
        h_search_layout.addStretch()
        h_search_layout.addWidget(self.home_search)
        h_search_layout.setSpacing(10)
        h_search_layout.addWidget(search_btn)
        h_search_layout.addStretch()
        layout.addLayout(h_search_layout)

        # İndeksleme Durum Alanı
        self.status_container = QWidget()
        self.status_container.hide()
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(20, 10, 20, 10)
        
        self.status_label = QLabel(_("Scanning:"))
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
        layout = QVBoxLayout(page)
        layout.setContentsMargins(15, 10, 15, 10)

        # Üst Arama Çubuğu
        top_bar = QHBoxLayout()
        res_logo = ClickableLogo()
        res_pixmap = QPixmap(os.path.join(BASE_DIR, "Booble_logo.png"))
        res_logo.setPixmap(res_pixmap.scaled(75, 75, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        res_logo.clicked.connect(self.go_home_and_clear)
        top_bar.addWidget(res_logo)

        self.res_search = QLineEdit()
        self.res_search.setMinimumHeight(38)
        self.res_search.setFont(QFont("DejaVu Sans", 11))
        self.res_search.returnPressed.connect(lambda: self.execute_new_search(self.res_search.text()))
        top_bar.addWidget(self.res_search)
        
        btn_search = QPushButton(_("Search"))
        btn_search.setMinimumHeight(38)
        btn_search.clicked.connect(lambda: self.execute_new_search(self.res_search.text()))
        top_bar.addWidget(btn_search)
        layout.addLayout(top_bar)

        # Arama Modu Radyo Butonları
        self.filter_group = QButtonGroup(self)
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(5, 4, 5, 4)
        filter_layout.setSpacing(14)

        self.radio_all = QRadioButton(_("All"))
        self.radio_docs = QRadioButton(_("Documents only"))
        self.radio_images = QRadioButton(_("Images only"))
        self.radio_videos = QRadioButton(_("Videos only"))
        self.radio_audio = QRadioButton(_("Audio only"))

        self.radio_all.setChecked(True)

        self.filter_group.addButton(self.radio_all)
        self.filter_group.addButton(self.radio_docs)
        self.filter_group.addButton(self.radio_images)
        self.filter_group.addButton(self.radio_videos)
        self.filter_group.addButton(self.radio_audio)

        filter_layout.addWidget(self.radio_all)
        filter_layout.addWidget(self.radio_docs)
        filter_layout.addWidget(self.radio_images)
        filter_layout.addWidget(self.radio_videos)
        filter_layout.addWidget(self.radio_audio)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Radyo butonlarına tıklandığında aramayı anında filtrele
        self.radio_all.toggled.connect(lambda checked: checked and self.on_filter_changed("all"))
        self.radio_docs.toggled.connect(lambda checked: checked and self.on_filter_changed("docs"))
        self.radio_images.toggled.connect(lambda checked: checked and self.on_filter_changed("images"))
        self.radio_videos.toggled.connect(lambda checked: checked and self.on_filter_changed("videos"))
        self.radio_audio.toggled.connect(lambda checked: checked and self.on_filter_changed("audio"))

        # Sonuç İstatistik Bilgisi
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #70757a; font-size: 9.5pt; padding-left: 5px;")
        layout.addWidget(self.stats_label)

        # Sonuçlar Alanı
        self.results_area = QTextBrowser()
        self.results_area.setOpenLinks(False)
        self.results_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_area.anchorClicked.connect(self.handle_link_click)
        self.results_area.customContextMenuRequested.connect(self.show_context_menu)
        self.results_area.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.results_area)

        # Ana sayfadakiyle birebir aynı standart Qt meşguliyet çubuğu
        self.search_busybar = QProgressBar()
        self.search_busybar.setRange(0, 0)
        self.search_busybar.setMinimumHeight(20)
        self.search_busybar.setMinimumWidth(300)
        self.search_busybar.setTextVisible(False)
        self.search_busybar.hide()
        layout.addWidget(self.search_busybar, alignment=Qt.AlignmentFlag.AlignCenter)

        # Google Tarzı Sayfalama Çubuğu
        self.pagination_layout = QHBoxLayout()
        self.pagination_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pagination_layout.setContentsMargins(0, 8, 0, 16)
        self.pagination_layout.setSpacing(6)
        layout.addLayout(self.pagination_layout)
        
        self.stack.addWidget(page)


    def clear_results_view(self):
        """Arama ekranındaki tüm eski sonuçları, sayaçları ve sayfalamayı sıfırlar."""
        # Eğer arka planda halen çalışan eski bir arama varsa sinyalini kes
        if hasattr(self, 'search_worker') and self.search_worker.isRunning():
            try:
                self.search_worker.results_ready.disconnect()
            except TypeError:
                pass
            self.search_worker.terminate()
            self.search_worker.wait(100)

        self.results_area.clear()
        self.stats_label.clear()
        self.update_pagination_ui(0)

    def go_home_and_clear(self):
        """Arama kutularını ve tüm eski sonuçları temizleyerek ana sayfaya döner."""
        self.clear_results_view()
        self.home_search.clear()
        self.res_search.clear()
        self.current_query = ""
        self.current_page = 1
        self.radio_all.setChecked(True)
        self.current_filter = "all"
        self.stack.setCurrentIndex(0)
        self.history_stack = [0]

    def go_back(self):
        if len(self.history_stack) > 1:
            self.history_stack.pop()
            self.stack.setCurrentIndex(self.history_stack[-1])
            if self.stack.currentIndex() == 0:
                self.clear_results_view()
                self.home_search.clear()
                self.current_query = ""

    def initiate_search(self):
        query = self.home_search.text().strip()
        if query:
            self.clear_results_view()
            self.res_search.setText(query)
            self.stack.setCurrentIndex(1)
            self.history_stack.append(1)
            self.execute_new_search(query)

    def execute_new_search(self, query):
        cleaned_query = query.strip()
        if not cleaned_query:
            return
        self.clear_results_view()
        self.current_query = cleaned_query
        self.current_page = 1
        self.fetch_results()

    

    def fetch_results(self):
        if not self.current_query:
            return

        # Arama esnasında doğal animasyonlu çubuğu göster
        self.search_busybar.show()

        config_path = os.path.expanduser("~/.config/Booble")
        db_path = os.path.join(config_path, "booble_index.db")

        # Aramayı seçili filtre moduna göre QThread arka planında başlat
        self.search_worker = SearchWorker(
            db_path=db_path,
            query=self.current_query,
            page=self.current_page,
            page_size=self.page_size,
            filter_type=self.current_filter
        )
        self.search_worker.results_ready.connect(self.on_search_completed)
        self.search_worker.start()

    def on_filter_changed(self, filter_type):
        if not self.current_query:
            return
        self.clear_results_view()
        self.current_filter = filter_type
        self.current_page = 1
        self.fetch_results()

    def on_search_completed(self, rows, total_results, page):
        self.total_results = total_results
        self.current_page = page

        total_pages = max(1, math.ceil(self.total_results / self.page_size))
        stats_text = _("About {count} results found (Page {current} / {total})").format(
            count=f"{self.total_results:,}",
            current=self.current_page,
            total=total_pages
        )
        self.stats_label.setText(stats_text)

        # Önce sonuçlar ve thumbnail'ler çizilsin
        self.display_page_results(rows)
        self.update_pagination_ui(total_pages)

        # Sonuçlar ekrana basıldıktan sonra çubuğu gizle
        self.search_busybar.hide()

    def display_page_results(self, rows):
        palette = self.palette()
        link_color = palette.color(palette.ColorGroup.Active, palette.ColorRole.Link).name()
        text_color = palette.color(palette.ColorGroup.Active, palette.ColorRole.WindowText).name()
        path_color = "#006621"

        if not rows:
            no_match_h3 = _("No files matched your search.")
            no_match_p = _("Suggestion: Try different keywords or re-index your system.")
            self.results_area.setHtml(
                f"<div style='font-family: sans-serif; padding: 20px; color: {text_color};'>"
                f"<h3>{no_match_h3}</h3>"
                f"<p style='color: #70757a;'>{no_match_p}</p>"
                "</div>"
            )
            return

        html_blocks = [
            f"<div style='font-family: sans-serif; padding: 10px; color: {text_color};'>"
        ]

        for raw_title, raw_path in rows:
            # HTML ve tırnak korumaları
            title = html.escape(raw_title)
            safe_display_path = html.escape(raw_path)
            safe_href = raw_path.replace('"', '&quot;')

            is_dir = os.path.isdir(raw_path)
            meta_parts = []

            # Dosya bilgilerini topla (Boyut ve Tarih)
            try:
                info = QFileInfo(raw_path)
                if not is_dir and info.exists():
                    meta_parts.append(human_readable_size(info.size()))
                    mtime = info.lastModified().toString("dd.MM.yyyy HH:mm")
                    meta_parts.append(mtime)
            except:
                pass

            meta_text = " • ".join(meta_parts)

            # Sistem temasından ikonu çek
            sys_icon_file = get_system_theme_icon_path(is_dir, raw_path)
            icon_tag = f'<img src="file://{sys_icon_file}" width="18" height="18" style="vertical-align: middle; margin-right: 6px;">' if sys_icon_file else ""

            # Resim veya Video önizleme kontrolü
            thumb_file, media_type = (None, None) if is_dir else get_thumbnail_path(raw_path)

            if thumb_file:
                # Sol tarafa yaslı, 140x90 geniş 16:9 Medya Kartı
                type_badge = _("VIDEO") if media_type == "video" else _("IMAGE")
                badge_bg = "#d93025" if media_type == "video" else "#1a73e8"

                # Video ve görseller için zenginleştirilmiş teknik bilgiler (İngilizce formatında)
                media_meta = get_media_metadata(raw_path, media_type)
                extra_meta_text = " • ".join(media_meta)
                if extra_meta_text:
                    full_meta_text = f"{meta_text} • <span style='color: #5f6368;'>{extra_meta_text}</span>"
                else:
                    full_meta_text = meta_text

                block = f"""
                <table style='margin-bottom: 20px; border-collapse: separate; border-spacing: 0; background-color: rgba(128,128,128,0.04); border-radius: 8px; border: 1px solid rgba(128,128,128,0.18); width: 100%;' cellpadding='8'>
                    <tr>
                        <td style='vertical-align: top; width: 142px; padding-right: 12px;'>
                            <div style='position: relative; width: 140px; height: 92px;'>
                                <a href="{safe_href}">
                                    <img src="file://{thumb_file}" width="140" height="92" style="border-radius: 6px; border: 1px solid #aaa; object-fit: cover; display: block;">
                                </a>
                            </div>
                        </td>
                        <td style='vertical-align: top;'>
                            <div style='margin-bottom: 3px;'>
                                <span style='background-color: {badge_bg}; color: #ffffff; font-size: 7.5pt; font-weight: bold; padding: 2px 6px; border-radius: 3px; vertical-align: middle; margin-right: 6px;'>{type_badge}</span>
                                {icon_tag}
                                <a href="{safe_href}" style="color: {link_color}; font-size: 13pt; text-decoration: none; font-weight: bold;">{title}</a>
                            </div>
                            <div style='color: {path_color}; font-size: 9.5pt; margin-bottom: 4px; word-break: break-all;'>{safe_display_path}</div>
                            <div style='color: #70757a; font-size: 9pt;'>{full_meta_text}</div>
                        </td>
                    </tr>
                </table>
                """
            else:
                # Standart dosya ve klasör kartı (Sistem teması ikonuyla)
                block = f"""
                <div style='margin-bottom: 16px; padding-left: 4px;'>
                    <div style='margin-bottom: 2px;'>
                        {icon_tag}
                        <a href="{safe_href}" style="color: {link_color}; font-size: 13pt; text-decoration: none;">{title}</a>
                    </div>
                    <div style='color: {path_color}; font-size: 9.5pt; margin-bottom: 3px; word-break: break-all;'>{safe_display_path}</div>
                    <div style='color: #70757a; font-size: 9pt;'>{meta_text}</div>
                </div>
                """
            html_blocks.append(block)

        html_blocks.append("</div>")
        self.results_area.setHtml("".join(html_blocks))
        self.results_area.verticalScrollBar().setValue(0)

    def update_pagination_ui(self, total_pages):
        # Eski sayfalama butonlarını temizle
        while self.pagination_layout.count():
            item = self.pagination_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if total_pages <= 1:
            return

        # Sistemin o anki aktif renklerini al (Koyu/Açık Tema Uyumu)
        pal = self.palette()
        btn_bg = pal.color(pal.ColorGroup.Active, pal.ColorRole.Button).name()
        btn_fg = pal.color(pal.ColorGroup.Active, pal.ColorRole.ButtonText).name()
        link_color = pal.color(pal.ColorGroup.Active, pal.ColorRole.Link).name()
        border_color = pal.color(pal.ColorGroup.Active, pal.ColorRole.Mid).name()

        nav_btn_style = f"""
            QPushButton {{
                height: 34px;
                padding-left: 12px;
                padding-right: 12px;
                font-size: 10pt;
                border: 1px solid {border_color};
                border-radius: 4px;
                background-color: {btn_bg};
                color: {btn_fg};
            }}
            QPushButton:hover {{
                border-color: {link_color};
            }}
        """

        # "Önceki" Butonu
        if self.current_page > 1:
            btn_prev = QPushButton(_("< Previous"))
            btn_prev.setStyleSheet(nav_btn_style)
            btn_prev.clicked.connect(lambda: self.change_page(self.current_page - 1))
            self.pagination_layout.addWidget(btn_prev)

        # Sayfa numaraları aralığı (Örn: 1 2 3 4 5...)
        start_p = max(1, self.current_page - 4)
        end_p = min(total_pages, start_p + 8)

        for p in range(start_p, end_p + 1):
            btn_page = QPushButton(str(p))
            btn_page.setFixedSize(36, 36)

            if p == self.current_page:
                btn_page.setEnabled(False)
                btn_page.setStyleSheet("""
                    QPushButton {
                        background-color: #fbbc04;
                        color: #1a1a1a;
                        font-size: 11pt;
                        font-weight: bold;
                        border: 2px inset #b58900;
                        border-radius: 4px;
                        padding-top: 2px;
                        padding-left: 2px;
                    }
                """)
            else:
                btn_page.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {btn_bg};
                        color: {link_color};
                        font-size: 10.5pt;
                        font-weight: bold;
                        border: 1px solid {border_color};
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        border-color: {link_color};
                    }}
                """)

            btn_page.clicked.connect(lambda checked, page_num=p: self.change_page(page_num))
            self.pagination_layout.addWidget(btn_page)

        # "Sonraki" Butonu
        if self.current_page < total_pages:
            btn_next = QPushButton(_("Next >"))
            btn_next.setStyleSheet(nav_btn_style)
            btn_next.clicked.connect(lambda: self.change_page(self.current_page + 1))
            self.pagination_layout.addWidget(btn_next)

    def change_page(self, new_page):
        self.clear_results_view()
        self.current_page = new_page
        self.fetch_results()

    def handle_link_click(self, url):
        self.open_file(url)

    def open_file(self, url):
        # url nesnesi QUrl veya str gelebilir (PyQt6 uyumluluğu)
        if hasattr(url, 'toLocalFile'):
            file_path = url.toLocalFile()
        else:
            file_path = str(url)

        if not file_path or file_path.startswith("file://"):
            raw_path = url.toString() if hasattr(url, 'toString') else str(url)
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
        if hasattr(self, 'indexer_thread') and self.indexer_thread.isRunning():
            QMessageBox.warning(self, _("Booble"), _("An indexing process is already running."))
            return

        if self.settings.get("scan_mode") == "custom" and self.settings.get("custom_path"):
            target_folder = self.settings.get("custom_path")
        else:
            target_folder = "/"

        config_path = os.path.expanduser("~/.config/Booble")
        db_path = os.path.join(config_path, "booble_index.db")

        # İlerleme çubuğunu belirsiz (marquee / busy) moduna alıyoruz
        self.pbar.setRange(0, 0)
        self.current_path_label.setText(_("Starting scan..."))
        self.status_container.show()

        self.indexer_thread = IndexWorker(
            db_path=db_path,
            target_folder=target_folder,
            user_excludes=self.settings.get("user_excludes", [])
        )
        self.indexer_thread.progress.connect(self.on_index_progress)
        self.indexer_thread.finished.connect(self.on_index_finished)
        self.indexer_thread.start()

    def show_context_menu(self, pos):
        anchor = self.results_area.anchorAt(pos)
        if not anchor:
            return

        menu = QMenu()
        
        open_act = QAction(_("Open"), self)
        open_act.triggered.connect(lambda: self.open_file(anchor))
        menu.addAction(open_act)

        open_folder_act = QAction(_("Open Containing Folder"), self)
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

    def change_language(self, lang_code):
        if self.settings.get("language") == lang_code:
            return

        self.settings["language"] = lang_code
        self.save_settings()

        QMessageBox.information(
            self,
            _("Language Changed"),
            _("Please restart Booble for the language changes to take effect.")
        )

    def show_about_dialog(self):
        icon_path = os.path.join(BASE_DIR, "boobleicon.png")

        dialog = QDialog(self)
        dialog.setWindowTitle(_("About Booble"))
        dialog.setWindowIcon(QIcon(icon_path))
        dialog.setFixedSize(490, 480)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        layout = QVBoxLayout(dialog)

        palette = self.palette()
        text_color = palette.color(palette.ColorGroup.Active, palette.ColorRole.WindowText).name()
        link_color = palette.color(palette.ColorGroup.Active, palette.ColorRole.Link).name()

        sub_title = _("Local Desktop Search Engine")
        label_version = _("Version:")
        label_license = _("License:")
        label_dev = _("Developer:")
        label_desc = _("Booble 2.0 is a high-performance local search engine that lets you find files, documents and multimedia on your computer in milliseconds.")
        feat_1 = _("Multi-threaded (QThread) and FTS5 based blazing-fast indexing")
        feat_2 = _("Rich media previews for images and videos")
        feat_3 = _("Filter modes for documents, images, videos and audio")
        feat_4 = _("Pagination and wildcard (*.ext) search support")
        disclaimer = _("This program is free software and comes with absolutely no warranty.")
        copyright_txt = _("Copyright © 2026 - A. Serhat KILIÇOĞLU")

        content = f"""
        <div style='font-family: DejaVu Sans, sans-serif; color: {text_color}; line-height: 1.45;'>
            <table style='border-collapse: collapse; margin-bottom: 8px;' cellpadding='0' cellspacing='0'>
                <tr>
                    <td style='vertical-align: middle; padding-right: 14px;'>
                        <img src="file://{icon_path}" width="52" height="52" style="display: block;">
                    </td>
                    <td style='vertical-align: middle;'>
                        <h2 style='color: #4285f4; margin: 0; font-size: 18pt;'>Booble</h2>
                        <div style='font-size: 9.5pt; color: #70757a;'>{sub_title}</div>
                    </td>
                </tr>
            </table>
            <hr style='border: none; border-top: 1px solid rgba(128,128,128,0.25);'>
            
            <p><b>{label_version}</b> 2.0.0<br>
            <b>{label_license}</b> GNU GPLv3<br>
            <b>{label_dev}</b> A. Serhat KILIÇOĞLU (shampuan)<br>
            <b>Github:</b> <a href="https://www.github.com/shampuan" style="color: {link_color};">www.github.com/shampuan</a></p>
            
            <p>{label_desc}</p>
            
            <p style='font-size: 9pt; color: #70757a;'>
            • {feat_1}<br>
            • {feat_2}<br>
            • {feat_3}<br>
            • {feat_4}
            </p>
            
            <p style='font-size: 8.5pt; color: #888;'><i>{disclaimer}</i></p>
            <p style='font-size: 9pt; color: #70757a; margin-bottom: 0;'>{copyright_txt}</p>
        </div>
        """
        
        label = QLabel(content)
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        btn_close = QPushButton(_("OK"))
        btn_close.setFixedWidth(110)
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)
        
        dialog.exec()

    def show_options_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_("Booble Options"))
        dialog.setFixedWidth(400)
        d_layout = QVBoxLayout(dialog)

        # Tarama Kapsamı Grubu
        group_box = QGroupBox(_("Scan Scope"))
        group_layout = QVBoxLayout()
        
        self.radio_all = QRadioButton(_("Entire System (/)"))
        self.radio_custom = QRadioButton(_("Custom Folder"))
        
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
        btn_browse = QPushButton(_("Browse..."))
        
        def browse_folder():
            folder = QFileDialog.getExistingDirectory(dialog, _("Select Scan Folder"))
            if folder:
                self.path_edit.setText(folder)
        
        btn_browse.clicked.connect(browse_folder)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(btn_browse)
        group_layout.addLayout(path_layout)
        group_box.setLayout(group_layout)
        d_layout.addWidget(group_box)

        # Kullanıcı Hariç Tutma Grubu
        exclude_box = QGroupBox(_("User Excluded Folders"))
        exclude_box_layout = QVBoxLayout()

        exclude_label_layout = QHBoxLayout()
        exclude_label_layout.addWidget(QLabel(_("Folders to exclude from scanning:")))
        
        btn_add_exclude = QPushButton("+")
        btn_add_exclude.setFixedWidth(30)
        btn_remove_exclude = QPushButton("-")
        btn_remove_exclude.setFixedWidth(30)
        
        exclude_label_layout.addStretch()
        exclude_label_layout.addWidget(btn_add_exclude)
        exclude_label_layout.addWidget(btn_remove_exclude)
        exclude_box_layout.addLayout(exclude_label_layout)

        self.exclude_list_widget = QListWidget()
        self.exclude_list_widget.addItems(self.settings.get("user_excludes", []))
        exclude_box_layout.addWidget(self.exclude_list_widget)

        # Güvenli Ekleme ve Çıkarma Fonksiyonları (Çakışma Önleyici)
        def add_exclude_path():
            folder = QFileDialog.getExistingDirectory(dialog, _("Select Folder to Exclude"))
            if not folder:
                return

            clean_folder = os.path.abspath(folder)

            # Güvenlik 1: Kök dizin engeli
            if clean_folder == "/":
                QMessageBox.warning(dialog, _("Warning"), _("The root directory (/) cannot be excluded."))
                return

            # Güvenlik 2: Özel klasör seçiliyse onunla çakışma kontrolü
            if self.radio_custom.isChecked() and self.path_edit.text():
                custom_target = os.path.abspath(self.path_edit.text())
                if clean_folder == custom_target:
                    QMessageBox.warning(dialog, _("Conflict Warning"), _("You cannot exclude the main folder you want to scan."))
                    return

            # Güvenlik 3: Zaten ekli mi?
            current_items = [self.exclude_list_widget.item(i).text() for i in range(self.exclude_list_widget.count())]
            if clean_folder not in current_items:
                self.exclude_list_widget.addItem(clean_folder)

        def remove_exclude_path():
            current_item = self.exclude_list_widget.currentItem()
            if current_item:
                self.exclude_list_widget.takeItem(self.exclude_list_widget.row(current_item))

        btn_add_exclude.clicked.connect(add_exclude_path)
        btn_remove_exclude.clicked.connect(remove_exclude_path)

        exclude_box.setLayout(exclude_box_layout)
        d_layout.addWidget(exclude_box)

        # Kaydet Butonu
        btn_save = QPushButton(_("Save Settings"))
        def save_and_close():
            self.settings["scan_mode"] = "custom" if self.radio_custom.isChecked() else "all"
            self.settings["custom_path"] = self.path_edit.text()
            self.settings["user_excludes"] = [
                self.exclude_list_widget.item(i).text() 
                for i in range(self.exclude_list_widget.count())
            ]
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
