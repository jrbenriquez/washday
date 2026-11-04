describe('Supply full and partial count',()=>{
 it('reconciles full count then leaves untouched supply unchanged in partial count',()=>{
  cy.visit('/supplies/');cy.get('[aria-label="Counted DEMO Detergent (cup)"]').type('12');cy.get('[aria-label="Counted DEMO Bag (piece)"]').type('34');cy.contains('button','Save stock count').click();cy.contains('[data-supply="DEMO Detergent"]','12').should('exist');cy.contains('[data-supply="DEMO Bag"]','34').should('exist');
  cy.get('[name=partial]').check();cy.get('[aria-label="Counted DEMO Detergent (cup)"]').type('11');cy.contains('button','Save stock count').click();cy.contains('[data-supply="DEMO Detergent"]','11').should('exist');cy.contains('[data-supply="DEMO Bag"]','34').should('exist');cy.contains('summary','Full').should('exist');cy.contains('summary','Partial').should('exist');
 });
});
