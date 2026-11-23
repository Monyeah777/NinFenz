package dev.ninfenz.mobile.ui.design

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/** 圆角阶：4/8/12/16/28，胶囊用 full。 */
object NfShape {
    val shapes = Shapes(
        extraSmall = RoundedCornerShape(Radius.xs.dp),
        small = RoundedCornerShape(Radius.sm.dp),
        medium = RoundedCornerShape(Radius.md.dp),
        large = RoundedCornerShape(Radius.lg.dp),
        extraLarge = RoundedCornerShape(Radius.xl.dp)
    )

    val pill = RoundedCornerShape(percent = 50)
}
