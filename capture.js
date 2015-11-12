var casper = require('casper').create();
casper.options.viewportSize = {width: 1200, height: 768};

var x = require('casper').selectXPath;

var url = casper.cli.get('url');
var j_user = casper.cli.get('juser')
var j_pwd = casper.cli.get('jpwd')
var out = casper.cli.get('out')

casper.start(url, function() {
  casper.wait(3000, function(){});
  this.fill(x('//*[@id="main-panel-content"]/div/form'), {
    'j_username': j_user,
    'j_password': j_pwd
  }, true);
});

casper.wait(5000, function(){
  this.capture(out, undefined,
  {
    format: 'jpg',
    quality: 100
  });
  console.log('Captured');
});

casper.run();