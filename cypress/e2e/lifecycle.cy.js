// Requires the labelled DEV-ONLY shop in full mode with idle DEMO W1/D1.
describe('Job-board machine lifecycle',()=>{
 it('starts job loads on the board, monitors/unloads on Machines and claims once',()=>{
  cy.visit('/jobs/new/');cy.contains('label','DEMO Wash-dry-fold').find('input').check();cy.get('[name=kg]').clear().type('3.0');cy.get('[name=customer_name]').type('DEMO Cypress lifecycle');cy.contains('button','Create job & show stub').click();
  cy.location('pathname').should('match',/\/jobs\/\d+\//).then(path=>{
   const number=path.split('/')[2];const card=()=>cy.get(`[data-job="${number}"]`);
   cy.visit('/jobs/');card().contains('button','Next · Washing').click();cy.contains('button','Start W1').click();
   cy.visit('/machines/');cy.contains('button','Start job').should('not.exist');cy.contains('button','Unload W1').click();
   cy.visit('/jobs/');card().contains('button','Next · Drying').click();cy.contains('button','Start D1').click();
   cy.visit('/machines/');cy.contains('button','Unload D1').click();
   cy.visit('/jobs/');card().contains('button','Next · Ready').click();card().contains('a','Claim').click();cy.get('[name=pay_method]').select('cash');cy.contains('button','Confirm claim').click();cy.contains('article','Claimed').should('exist');
   cy.visit('/jobs/');cy.get(`[data-job="${number}"]`).should('not.exist');cy.visit(`/jobs/${number}/history/`);cy.contains('Loaded W1').should('exist');cy.contains('Loaded D1').should('exist');cy.contains('Released').should('exist');
  });
 });
});
