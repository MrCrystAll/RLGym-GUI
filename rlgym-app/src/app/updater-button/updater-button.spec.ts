import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UpdaterButton } from './updater-button';

describe('UpdaterButton', () => {
  let component: UpdaterButton;
  let fixture: ComponentFixture<UpdaterButton>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UpdaterButton],
    }).compileComponents();

    fixture = TestBed.createComponent(UpdaterButton);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
