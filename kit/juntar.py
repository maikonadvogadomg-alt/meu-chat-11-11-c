# -*- coding: utf-8 -*-
"""
JUNTAR — transforma um projeto "em pedaços" (index.html + pasta css + pasta js)
num ARQUIVO HTML ÚNICO, que abre sozinho em qualquer lugar (até sem servidor).

Como usar (no terminal do VS Code):
    python kit/juntar.py  PASTA-DO-PROJETO
Exemplo:
    python kit/juntar.py  index-modular
Sai o arquivo  index-modular-UNICO.html  ao lado da pasta. A pasta original não muda.
"""
import os, re, sys, base64, mimetypes

EXTERNO = re.compile(r'^(?:[a-z][\w+.-]*:|//|#|data:)', re.I)


def juntar(pasta, pagina='index.html'):
    pasta = os.path.abspath(pasta)
    index = os.path.join(pasta, pagina)
    if not os.path.isfile(index):
        sys.exit('❌ Não achei o ' + pagina + ' dentro de: ' + pasta)
    html = open(index, encoding='utf-8', errors='replace').read()
    usados, faltando = [], []

    def ler(rel):
        if EXTERNO.match(rel):
            return None   # da internet: deixa como está
        c = os.path.normpath(os.path.join(pasta, rel.split('?')[0].split('#')[0].lstrip('/')))
        if not c.startswith(pasta) or not os.path.isfile(c):
            faltando.append(rel)
            return None
        usados.append(rel)
        return c

    def css(m):
        href = re.search(r'href\s*=\s*["\']([^"\']+)', m.group(0))
        c = href and ler(href.group(1))
        if not c:
            return m.group(0)
        texto = open(c, encoding='utf-8', errors='replace').read()
        de = os.path.relpath(os.path.dirname(c), pasta).replace('\\', '/')
        if de and de != '.':   # url(../img/x.png) dentro de css/ volta a ser img/x.png
            def fix(u):
                u = u.strip()
                if EXTERNO.match(u) or u.startswith('/'):
                    return u
                return os.path.normpath(os.path.join(de, u)).replace('\\', '/')
            texto = re.sub(r'url\(\s*(["\']?)([^"\')]+)\1\s*\)', lambda x: 'url(' + x.group(1) + fix(x.group(2)) + x.group(1) + ')', texto)
        media = re.search(r'\bmedia\s*=\s*(["\'][^"\']*["\'])', m.group(0), re.I)
        return '<style' + (' media=' + media.group(1) if media else '') + '>/* ' + href.group(1) + ' */\n' + texto + '\n</style>'
    html = re.sub(r'<link\b[^>]*rel\s*=\s*["\']?stylesheet[^>]*>', css, html, flags=re.I)

    def js(m):
        abre = m.group(1)
        src = re.search(r'\bsrc\s*=\s*["\']([^"\']+)', abre)
        c = src and ler(src.group(1))
        if not c:
            return m.group(0)
        codigo = open(c, encoding='utf-8', errors='replace').read()
        if re.search(r'type\s*=\s*["\']?module', abre, re.I) and re.search(r'(\bfrom\s*|\bimport\s*\(?\s*)["\']\.\.?/', codigo):
            return m.group(0)  # módulo que importa outros arquivos: fica como está
        resto = re.sub(r'\s*\bsrc\s*=\s*["\'][^"\']+["\']', '', abre)
        resto = re.sub(r'\s+(async|defer)\b', '', resto, flags=re.I)
        codigo = codigo.replace('</script', '<\\/script').replace('<!--', '<\\x21--')
        return resto + '\n/* ' + src.group(1) + ' */\n' + codigo + '\n</script>'
    html = re.sub(r'(<script\b[^>]*\bsrc\s*=[^>]*>)\s*</script>', js, html, flags=re.I)

    def img(m):
        rel = m.group(2)
        c = ler(rel)
        if not c or os.path.getsize(c) > 300 * 1024:
            return m.group(0)
        tipo = mimetypes.guess_type(c)[0] or 'application/octet-stream'
        return m.group(1) + 'data:' + tipo + ';base64,' + base64.b64encode(open(c, 'rb').read()).decode() + m.group(3)
    html = re.sub(r'(<(?:img|link)\b[^>]*?(?:src|href)\s*=\s*["\'])((?:icons|img|imagens|assets)/[^"\']+)(["\'])', img, html, flags=re.I)

    saida = pasta.rstrip(os.sep) + '-UNICO.html'
    open(saida, 'w', encoding='utf-8').write(html)
    print('✅ Pronto:', saida)
    print('   Peças colocadas dentro:', len(usados))
    if faltando:
        print('⚠️  Não achei estas peças (ficaram como estavam):')
        for f in faltando:
            print('    -', f)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    juntar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'index.html')
