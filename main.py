import sys
import os
from pathlib import Path
import chardet

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QComboBox,
    QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


TEXT_EXTENSIONS = {
    ".txt", ".csv", ".json", ".xml", ".srt",
    ".md", ".log", ".ini", ".yaml", ".yml"
}


ENCODING_MAP = {
    "ANSI (GBK)": "gbk",
    "UTF-8": "utf-8",
    "UTF-8 with BOM": "utf-8-sig",
}


class ConvertWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(str)       # summary message

    def __init__(self, input_path, output_dir, target_encoding):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.target_encoding = target_encoding

    def run(self):
        success_count = 0
        ascii_count = 0
        skipped_count = 0
        fail_files = []

        files = self.collect_files(self.input_path)
        total_files = len(files)
        
        for i, file in enumerate(files):
            try:
                status, msg = self.convert_file(file, self.input_path, Path(self.output_dir), self.target_encoding)
                if status == "ascii":
                    ascii_count += 1
                    success_count += 1
                elif status == "skipped":
                    skipped_count += 1
                else:
                    success_count += 1
            except Exception as e:
                fail_files.append(f"{file.name}: {str(e)}")
            
            self.progress.emit(i + 1, total_files)

        # 结果汇总
        summary = f"处理完成！\n\n成功转换：{success_count} 个文件"
        if ascii_count > 0:
            summary += f"\n（其中 {ascii_count} 个为纯英文/数字文件，转换前后二进制一致）"
        
        if skipped_count > 0:
            summary += f"\n\n跳过 {skipped_count} 个文件（因包含目标编码不支持的字符，已保留原编码）"

        if fail_files:
            summary += f"\n\n失败 {len(fail_files)} 个文件（已跳过）：\n" + "\n".join(fail_files[:5])
            if len(fail_files) > 5:
                summary += "\n..."
        
        self.finished.emit(summary)

    def collect_files(self, path: Path):
        if path.is_file():
            return [path] if path.suffix.lower() in TEXT_EXTENSIONS else []
        files = []
        for p in path.rglob("*"):
            if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS:
                files.append(p)
        return files

    def detect_encoding(self, file_path: Path):
        with open(file_path, "rb") as f:
            raw = f.read()
        
        # 1. 优先尝试 UTF-8 (包括 BOM)
        if raw.startswith(b'\xef\xbb\xbf'):
            return "utf-8-sig"
            
        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass

        # 2. 获取 chardet 检测结果
        result = chardet.detect(raw)
        detected = result["encoding"]
        
        # 3. 智能修正：如果检测结果不是常见的 CJK 编码，但能用 GB18030 解码，则优先认定为 GB18030
        cjk_encodings = {'gb2312', 'gbk', 'gb18030', 'big5', 'shift_jis', 'euc-jp', 'euc-kr'}
        
        if detected and detected.lower() not in cjk_encodings:
            try:
                raw.decode("gb18030")
                return "gb18030"
            except UnicodeDecodeError:
                pass
        
        return detected or "utf-8"

    def convert_file(self, file: Path, input_root: Path, output_root: Path, target_encoding: str):
        src_encoding = self.detect_encoding(file)

        with open(file, "r", encoding=src_encoding, errors='replace') as f:
            content = f.read()
        
        # 1. 检测是否为纯 ASCII
        try:
            content.encode('ascii')
            # 纯 ASCII 无需转换，视为成功
            is_ascii = True
        except UnicodeEncodeError:
            is_ascii = False

        # 2. 检测目标编码是否支持
        try:
            content.encode(target_encoding)
            final_encoding = target_encoding
            status = "ascii" if is_ascii else "converted"
        except UnicodeEncodeError:
            # 不支持则保留原编码
            final_encoding = src_encoding
            status = "skipped"

        # 计算输出路径
        if output_root == input_root or not input_root.is_dir():
            out_path = file
        else:
            rel = file.relative_to(input_root)
            out_path = output_root / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)

        # 如果是原地修改且跳过，则无需写入
        if out_path == file and status == "skipped":
            return status, "Skipped (Incompatible)"

        # 写入文件
        with open(out_path, "w", encoding=final_encoding, errors='replace') as f:
            f.write(content)
            
        return status, "OK"


class DragLineEdit(QLineEdit):
    """支持拖拽文件 / 文件夹的输入框"""

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if paths:
            self.setText(paths[0])


class EncodingConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("批量文本编码转换工具")
        self.init_ui()

    def init_ui(self):
        # 输入路径
        self.input_edit = DragLineEdit()
        self.input_edit.setPlaceholderText("拖拽文件或文件夹到此处")

        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_input)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(browse_btn)

        # 编码选择
        self.encoding_combo = QComboBox()
        for k in ENCODING_MAP:
            self.encoding_combo.addItem(k)
        self.encoding_combo.setCurrentText("ANSI (GBK)")

        encoding_layout = QHBoxLayout()
        encoding_layout.addWidget(QLabel("目标编码："))
        encoding_layout.addWidget(self.encoding_combo)

        # 开始按钮
        self.start_btn = QPushButton("开始转换")
        self.start_btn.clicked.connect(self.start_convert)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        # 主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 0, 10, 10)
        layout.setSpacing(0)

        layout.addWidget(QLabel("原始文本路径："))
        layout.addLayout(input_layout)
        
        layout.addSpacing(10)
        layout.addLayout(encoding_layout)
        layout.addSpacing(10)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.progress_bar)
        layout.addStretch()

        self.setLayout(layout)
        
        # 调整窗口大小
        self.setFixedWidth(520)
        self.adjustSize()

    def browse_input(self):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            self.input_edit.setText(path)

    def start_convert(self):
        input_path = self.input_edit.text().strip()
        if not input_path:
            QMessageBox.warning(self, "提示", "请先选择文件或文件夹")
            return

        input_path = Path(input_path)
        if not input_path.exists():
            QMessageBox.warning(self, "错误", "路径不存在")
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录（不修改则覆盖原文件）",
            str(input_path if input_path.is_dir() else input_path.parent)
        )

        if not output_dir:
            return

        target_encoding = ENCODING_MAP[self.encoding_combo.currentText()]

        # UI 状态更新
        self.start_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 启动后台线程
        self.worker = ConvertWorker(input_path, output_dir, target_encoding)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.conversion_finished)
        self.worker.start()

    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def conversion_finished(self, summary):
        self.start_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "完成", summary)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EncodingConverter()
    window.show()
    sys.exit(app.exec())
