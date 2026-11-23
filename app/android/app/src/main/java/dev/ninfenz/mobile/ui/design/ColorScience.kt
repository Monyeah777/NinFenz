package dev.ninfenz.mobile.ui.design

import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

/** sRGB → CIE Lab (D65) 与 CIEDE2000；比 RGB 欧氏距离更接近感知差。 */
object ColorScience {
    private fun linear(c: Int): Double {
        val s = c / 255.0
        return if (s <= 0.04045) s / 12.92 else ((s + 0.055) / 1.055).pow(2.4)
    }

    fun lab(argb: Int): Triple<Double, Double, Double> {
        val r = linear((argb shr 16) and 0xFF)
        val g = linear((argb shr 8) and 0xFF)
        val b = linear(argb and 0xFF)
        val x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
        val y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
        val z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
        fun f(t: Double) = if (t > 0.008856) t.pow(1.0 / 3.0) else 7.787 * t + 16.0 / 116.0
        val fx = f(x); val fy = f(y); val fz = f(z)
        return Triple(116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))
    }

    fun deltaE2000(a: Int, b: Int): Double {
        val (l1, a1, b1) = lab(a)
        val (l2, a2, b2) = lab(b)
        val c1 = sqrt(a1 * a1 + b1 * b1)
        val c2 = sqrt(a2 * a2 + b2 * b2)
        val cBar = (c1 + c2) / 2
        val g = 0.5 * (1 - sqrt(cBar.pow(7) / (cBar.pow(7) + 25.0.pow(7))))
        val a1p = (1 + g) * a1
        val a2p = (1 + g) * a2
        val c1p = sqrt(a1p * a1p + b1 * b1)
        val c2p = sqrt(a2p * a2p + b2 * b2)
        fun hue(ap: Double, bp: Double): Double {
            if (ap == 0.0 && bp == 0.0) return 0.0
            var h = Math.toDegrees(atan2(bp, ap))
            if (h < 0) h += 360
            return h
        }
        val h1p = hue(a1p, b1)
        val h2p = hue(a2p, b2)
        val dLp = l2 - l1
        val dCp = c2p - c1p
        var dhp = 0.0
        if (c1p * c2p != 0.0) {
            dhp = h2p - h1p
            if (dhp > 180) dhp -= 360
            if (dhp < -180) dhp += 360
        }
        val dHp = 2 * sqrt(c1p * c2p) * sin(Math.toRadians(dhp / 2))
        val lBar = (l1 + l2) / 2
        val cBarp = (c1p + c2p) / 2
        var hBar = h1p + h2p
        if (c1p * c2p != 0.0) {
            if (kotlin.math.abs(h1p - h2p) <= 180) hBar = (h1p + h2p) / 2
            else if (h1p + h2p < 360) hBar = (h1p + h2p + 360) / 2
            else hBar = (h1p + h2p - 360) / 2
        }
        val t = 1 - 0.17 * cos(Math.toRadians(hBar - 30)) +
            0.24 * cos(Math.toRadians(2 * hBar)) +
            0.32 * cos(Math.toRadians(3 * hBar + 6)) -
            0.20 * cos(Math.toRadians(4 * hBar - 63))
        val dTheta = 30 * exp(-((hBar - 275) / 25).pow(2))
        val rc = 2 * sqrt(cBarp.pow(7) / (cBarp.pow(7) + 25.0.pow(7)))
        val sl = 1 + 0.015 * (lBar - 50).pow(2) / sqrt(20 + (lBar - 50).pow(2))
        val sc = 1 + 0.045 * cBarp
        val sh = 1 + 0.015 * cBarp * t
        val rt = -sin(Math.toRadians(2 * dTheta)) * rc
        val dl = dLp / sl
        val dc = dCp / sc
        val dh = dHp / sh
        return sqrt(dl * dl + dc * dc + dh * dh + rt * dc * dh)
    }
}
