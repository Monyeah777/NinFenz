# 反射入口必须保留；base 通过 Class.forName("dev.ninfenz.mobile.ocr.OcrFeature") 调用。
-keep class dev.ninfenz.mobile.ocr.OcrFeature { public static *; }
-keep class dev.ninfenz.mobile.ocr.ImageOcrImporter { *; }
-keep class dev.ninfenz.mobile.ocr.PdfOcrFeature { *; }
