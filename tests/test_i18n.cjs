const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const filename = path.join(__dirname, '../assets/i18n.js');
assert.ok(fs.existsSync(filename), 'Localization module must exist');
const {entries, translate, toEnglish} = require(filename);
assert.equal(translate('Legendas'), 'Subtitles');
assert.equal(translate('Legendas', 'invalid'), 'Subtitles');
assert.equal(translate('Subtitles', 'pt'), 'Legendas');
assert.equal(translate('Legendas', 'es'), 'Subtítulos');
assert.equal(translate('Appearance', 'pt'), 'Aparência');
assert.equal(translate('Load selected', 'es'), 'Cargar selección');
const payload = 'Duna.{label}.$&.$1.${evil}.ação.[a-z]+.mkv';
assert.equal(translate('Playing: ' + payload, 'pt'), 'Reproduzindo: ' + payload);
assert.equal(translate('Reproduzindo: ' + payload, 'es'), 'Reproduciendo: ' + payload);
assert.equal(toEnglish('Reproduciendo: ' + payload), 'Playing: ' + payload);
assert.equal(translate('Subtitle loaded: ' + payload + '. Adjust the delay if needed.', 'es'), 'Subtítulo cargado: ' + payload + '. Ajusta el retraso si es necesario.');
assert.equal(translate('Reproduzindo: ', 'es'), 'Reproduciendo: ');
assert.equal(toEnglish('. Se necessário, ajuste o atraso acima.'), '. Adjust the delay above if needed.');
assert.equal(translate(' Escolha outra legenda na lista.', 'es'), ' Elige otro subtítulo de la lista.');
for (const metadata of [payload, 'C:\\Movies\\Legendas\\ação.mkv', 'https://example.com/Subtitles?name=Legendas', 'SubDL | Legendas.mkv', 'Off.mkv']) {
  assert.equal(translate(metadata, 'es'), metadata);
}
assert.equal(translate('7 subtitle(s) found. Select a release and choose Load selected.', 'pt'), '7 legenda(s) encontrada(s). Selecione uma versão e clique em Carregar seleção.');
assert.equal(translate('O servico respondeu com HTTP 429.', 'es'), 'El servicio respondió con HTTP 429.');
assert.equal(toEnglish('Resposta inesperada do servico.'), 'Unexpected response from the service.');
for (const row of entries) {
  assert.equal(row.length, 3);
  for (const phrase of row) assert.equal(toEnglish(phrase), row[0], 'Round trip: ' + phrase);
}
const browser = {};
vm.runInNewContext(fs.readFileSync(filename, 'utf8'), browser);
assert.equal(browser.PlayerI18n.translate('Legendas'), 'Subtitles');
console.log('Localization assertions passed (' + entries.length + ' entries, Node and browser).');
