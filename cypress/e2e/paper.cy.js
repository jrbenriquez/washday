describe('Paper sheet reconciliation', () => {
  it('keeps the paper number and original receipt day', () => {
    const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Manila' }).format(new Date(Date.now() - 86400000));
    cy.env(['paperRef']).then(({ paperRef }) => {
    const paper = paperRef || 'P-7';
    cy.visit('/jobs/new/?paper=1');
    cy.get('[name=paper_ref]').type(paper);
    cy.get('[name=paper_date]').type(day);
    cy.get('[name=received_time]').type('10:00');
    cy.get('[name=written_total]').type('105');
    cy.get('#kg').clear().type('3');
    cy.contains('button', 'Create job & show stub').click();
    cy.contains('article', paper).should('exist');
    cy.contains('a', 'Job timeline').click();
    cy.contains('Received on paper as ' + paper).should('exist');
    });
  });
});
