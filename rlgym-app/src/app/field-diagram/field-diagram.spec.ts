import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FieldDiagram } from './field-diagram';

describe('FieldDiagram', () => {
  let component: FieldDiagram;
  let fixture: ComponentFixture<FieldDiagram>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FieldDiagram],
    }).compileComponents();

    fixture = TestBed.createComponent(FieldDiagram);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
