const { defineConfig } = require('cypress');
module.exports=defineConfig({env:{deviceKey:'',paperRef:'P-7'},e2e:{baseUrl:'http://127.0.0.1:8000',supportFile:'cypress/support/e2e.js'},video:false,screenshotOnRunFailure:true});
