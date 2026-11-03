describe('Supply full and partial count',()=>{
 it('reconciles full count then leaves untouched supply unchanged in partial count',()=>{
  cy.visit('/supplies/');cy.contains('label','Counted DEMO Detergent').find('input').type('12');cy.contains('label','Counted DEMO Bag').find('input').type('34');cy.contains('button','Save stock count').click();cy.contains('[data-supply="DEMO Detergent"]','12').should('exist');cy.contains('[data-supply="DEMO Bag"]','34').should('exist');
  cy.get('[name=partial]').check();cy.contains('label','Counted DEMO Detergent').find('input').type('11');cy.contains('button','Save stock count').click();cy.contains('[data-supply="DEMO Detergent"]','11').should('exist');cy.contains('[data-supply="DEMO Bag"]','34').should('exist');cy.contains('summary','Full').should('exist');cy.contains('summary','Partial').should('exist');
 });
});
