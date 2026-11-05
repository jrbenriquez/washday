beforeEach(() => {
  cy.env(['deviceKey'], { log: false }).then(({ deviceKey }) => {
    if (deviceKey) cy.setCookie('washday_device', deviceKey, { log: false });
  });
});
