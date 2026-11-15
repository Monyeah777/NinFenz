package dev.ninfenz.studio.ui

import java.io.File
import javax.swing.JFileChooser
import javax.swing.filechooser.FileNameExtensionFilter

/** 极简 Swing 文件对话框（桌面读文件/选目录）。 */
object FileDialogs {

    fun openFile(title: String, vararg extensions: String): File? {
        val chooser = JFileChooser()
        chooser.dialogTitle = title
        chooser.fileSelectionMode = JFileChooser.FILES_ONLY
        if (extensions.isNotEmpty()) {
            chooser.fileFilter = FileNameExtensionFilter(extensions.joinToString(", "), *extensions)
        }
        return if (chooser.showOpenDialog(null) == JFileChooser.APPROVE_OPTION) chooser.selectedFile else null
    }

    fun openDirectory(title: String): File? {
        val chooser = JFileChooser()
        chooser.dialogTitle = title
        chooser.fileSelectionMode = JFileChooser.DIRECTORIES_ONLY
        return if (chooser.showOpenDialog(null) == JFileChooser.APPROVE_OPTION) chooser.selectedFile else null
    }
}
