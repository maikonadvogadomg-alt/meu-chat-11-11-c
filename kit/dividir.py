# -*- coding: utf-8 -*-
"""
DIVIDIR — transforma um HTML grande (tudo num arquivo só) numa versão MODULAR:
cada <style> vira um arquivo em css/ e cada <script> vira um arquivo em js/,
NA MESMA ORDEM. O arquivo original NÃO muda.

Como usar (no terminal do VS Code, dentro da pasta do projeto):
    python kit/dividir.py index.html
Sai a pasta  index-modular/  ao lado, com:
    index.html   (o HTML com <link> e <script src> no lugar do código)
    css/01-estilo.css, css/02-estilo.css ...
    js/01-codigo.js, js/02-codigo.js ...
    LEIA-MODULAR.txt  (o que foi feito e os avisos)

Por que não quebra: cada <script> continua um script separado, na mesma ordem,
igual estava dentro do HTML. Scripts especiais (React/Babel "text/babel", JSON,
modelos) ficam dentro do HTML, como estavam.
Depois teste com um servidor:   cd index-modular   e   npx serve
"""
import os, re, sys, shutil

EXTERNO = re.compile(r'^(?:[a-z][\w+.-]*:|//|#|data:|/)', re.I)


def normalizar(p):
    o = []
    for s in p.replace('\\', '/').split('/'):
        if not s or s == '.':
            continue
        if s == '..':
            if o:
                o.pop()
        else:
            o.append(s)
    return '/'.join(o)


def relativo(de_dir, para):
    a = de_dir.split('/') if de_dir else []
    b = para.split('/')
    i = 0
    while i < len(a) and i < len(b) - 1 and a[i] == b[i]:
        i += 1
    return '../' * (len(a) - i) + '/'.join(b[i:])


def mover_css(css, de_dir, para_dir):
    # url(...) e @import continuam apontando para o MESMO arquivo depois que o CSS muda de pasta
    def fix(u):
        u = u.strip()
        if EXTERNO.match(u):
            return u
        return relativo(para_dir, normalizar((de_dir + '/' if de_dir else '') + u))
    css = re.sub(r'url\(\s*(["\']?)([^"\')]+)\1\s*\)', lambda m: 'url(' + m.group(1) + fix(m.group(2)) + m.group(1) + ')', css)
    css = re.sub(r'@import\s+(["\'])([^"\']+)\1', lambda m: '@import ' + m.group(1) + fix(m.group(2)) + m.group(1), css)
    return css


def dividir(caminho):
    caminho = os.path.abspath(caminho)
    if not os.path.isfile(caminho):
        sys.exit('❌ Não achei o arquivo: ' + caminho)
    html = open(caminho, encoding='utf-8', errors='replace').read()
    base = os.path.splitext(os.path.basename(caminho))[0]
    pasta_orig = os.path.dirname(caminho)
    saida = os.path.join(pasta_orig, base + '-modular')
    if os.path.exists(saida):
        shutil.rmtree(saida)
    os.makedirs(os.path.join(saida, 'css'))
    os.makedirs(os.path.join(saida, 'js'))
    feitos, avisos, n = [], [], {'css': 0, 'js': 0}

    def estilo(m):
        at, css = m.group(1), m.group(2)
        if not css.strip():
            return m.group(0)
        n['css'] += 1
        nome = '%02d-estilo.css' % n['css']
        open(os.path.join(saida, 'css', nome), 'w', encoding='utf-8').write(mover_css(css.lstrip('\n'), '', 'css'))
        media = re.search(r'\bmedia\s*=\s*(["\'][^"\']*["\'])', at, re.I)
        feitos.append('css/%s (%d linhas)' % (nome, css.count('\n') + 1))
        return '<link rel="stylesheet" href="css/' + nome + '"' + (' media=' + media.group(1) if media else '') + '>'
    html = re.sub(r'<style\b([^>]*)>([\s\S]*?)</style>', estilo, html, flags=re.I)

    def script(m):
        at, js = m.group(1), m.group(2)
        if re.search(r'\bsrc\s*=', at, re.I) or not js.strip():
            return m.group(0)
        t = re.search(r'\btype\s*=\s*["\']?([^"\'\s>]+)', at, re.I)
        tipo = t.group(1).lower() if t else ''
        if tipo and tipo not in ('text/javascript', 'application/javascript', 'module'):
            avisos.append('Ficou dentro do HTML um <script type="%s"> (%s).' % (tipo, 'React/Babel: precisa ficar assim ou usar Vite' if 'babel' in tipo else 'não é JavaScript comum'))
            return m.group(0)
        if re.search(r'document\.currentScript|document\.write\s*\(', js):
            avisos.append('Ficou dentro do HTML um script que usa document.write ou currentScript (fora dele mudaria o comportamento).')
            return m.group(0)
        modulo = tipo == 'module'
        n['js'] += 1
        nome = '%02d-%s.%s' % (n['js'], 'modulo' if modulo else 'codigo', 'mjs' if modulo else 'js')
        if modulo:  # imports "./x.js" eram relativos ao HTML; agora o arquivo está em js/
            js = re.sub(r'(\bfrom\s*|\bimport\s*\(?\s*)(["\'])(\.\.?/[^"\']+)\2', lambda x: x.group(1) + x.group(2) + relativo('js', normalizar(x.group(3))) + x.group(2), js)
        open(os.path.join(saida, 'js', nome), 'w', encoding='utf-8').write(js.lstrip('\n'))
        outros = re.sub(r'\btype\s*=\s*["\']?[^"\'\s>]+["\']?', '', at, flags=re.I)
        outros = re.sub(r'\s+(async|defer)\b', '', outros, flags=re.I).strip()
        feitos.append('js/%s (%d linhas%s)' % (nome, js.count('\n') + 1, ', módulo' if modulo else ''))
        return '<script' + (' type="module"' if modulo else '') + ' src="js/' + nome + '"' + (' ' + outros if outros else '') + '></script>'
    html = re.sub(r'<script\b([^>]*)>([\s\S]*?)</script>', script, html, flags=re.I)

    if not feitos:
        shutil.rmtree(saida)
        sys.exit('ℹ️  Este HTML não tem <style> nem <script> dentro para dividir (talvez já seja modular).')
    open(os.path.join(saida, 'index.html' if base == 'index' else base + '.html'), 'w', encoding='utf-8').write(html)
    # leva junto as pastas de imagens/ícones que o HTML usa (o HTML continua achando)
    for pasta in ('icons', 'img', 'imagens', 'assets', 'fonts'):
        o = os.path.join(pasta_orig, pasta)
        if os.path.isdir(o):
            shutil.copytree(o, os.path.join(saida, pasta))
    for arq in os.listdir(pasta_orig):
        if re.search(r'\.(webmanifest|json|png|ico|svg)$', arq, re.I) or arq in ('manifest.json', 'sw.js'):
            o = os.path.join(pasta_orig, arq)
            if os.path.isfile(o):
                shutil.copy2(o, saida)
    leia = ['Versão modular de ' + os.path.basename(caminho) + ' (o original não mudou).', '', 'Arquivos criados:'] + ['  - ' + f for f in feitos]
    if avisos:
        leia += ['', 'Avisos:'] + ['  - ' + a for a in avisos]
    leia += ['', 'Para testar:  cd "' + os.path.basename(saida) + '"   e depois   npx serve   (ou: python -m http.server 5500)',
             'Para voltar a um arquivo só:  python kit/juntar.py "' + os.path.basename(saida) + '"']
    open(os.path.join(saida, 'LEIA-MODULAR.txt'), 'w', encoding='utf-8').write('\n'.join(leia) + '\n')
    print('✅ Pronto:', saida)
    for f in feitos:
        print('   ', f)
    for a in avisos:
        print('⚠️ ', a)
    print('\nAgora teste:  cd "%s"   e   npx serve' % os.path.basename(saida))


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    dividir(sys.argv[1])
