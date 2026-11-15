package dev.ninfenz.studio.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.ninfenz.studio.ui.screens.AuthorScreen
import dev.ninfenz.studio.ui.screens.PackManagerScreen
import dev.ninfenz.studio.ui.screens.PrintScreen
import dev.ninfenz.studio.ui.screens.ProjectManagerScreen
import dev.ninfenz.studio.ui.screens.ReviewScreen
import dev.ninfenz.studio.ui.screens.TuiTerminalScreen
import dev.ninfenz.studio.ui.screens.ValidationPanelScreen

enum class StudioScreen(val title: String) {
    PROJECTS("项目"),
    AUTHOR("作者"),
    PACKS("Pack"),
    REVIEW("评审"),
    VALIDATION("校验"),
    TUI("TUI"),
    PRINT("打印")
}

@Composable
fun NfStudioApp() {
    var screen by remember { mutableStateOf(StudioScreen.PROJECTS) }
    Row(modifier = Modifier.fillMaxSize()) {
        NavigationRail {
            for (item in StudioScreen.values()) {
                NavigationRailItem(
                    selected = screen == item,
                    onClick = { screen = item },
                    icon = { Text(item.title.take(1), style = MaterialTheme.typography.titleMedium) },
                    label = { Text(item.title) }
                )
            }
        }
        Column(modifier = Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("NF Studio · " + screen.title, style = MaterialTheme.typography.headlineSmall)
            when (screen) {
                StudioScreen.PROJECTS -> ProjectManagerScreen()
                StudioScreen.AUTHOR -> AuthorScreen()
                StudioScreen.PACKS -> PackManagerScreen()
                StudioScreen.REVIEW -> ReviewScreen()
                StudioScreen.VALIDATION -> ValidationPanelScreen()
                StudioScreen.TUI -> TuiTerminalScreen()
                StudioScreen.PRINT -> PrintScreen()
            }
        }
    }
}
