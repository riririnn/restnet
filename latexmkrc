# LuaLaTeX (luatexja) でビルド
$pdf_mode = 4;   # 4 = lualatex
$lualatex = 'lualatex -interaction=nonstopmode -file-line-error -synctex=1 %O %S';
$out_dir  = 'build';
