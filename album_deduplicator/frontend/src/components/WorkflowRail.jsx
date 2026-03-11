import React from "react";
import { Steps } from "antd";

import { getWorkflowStepIndex } from "../workflow";

function buildStepTitle(step) {
  return (
    <span className="workflow-rail-title" data-testid={`workflow-step-${step.key}`}>
      <span className="workflow-rail-title-label">{step.title}</span>
      {step.badges?.length ? (
        <span className="workflow-rail-badges">
          {step.badges.map((badge, index) => (
            <React.Fragment key={`${step.key}-badge-${index}`}>
              {badge}
            </React.Fragment>
          ))}
        </span>
      ) : null}
    </span>
  );
}

export function WorkflowRail({ steps, activeStep, onNavigate }) {
  const current = getWorkflowStepIndex(activeStep);

  return (
    <div className="workflow-rail-shell" data-testid="workflow-rail">
      <div className="workflow-rail-inner">
        <Steps
          current={current}
          type="navigation"
          size="small"
          responsive={false}
          className="workflow-rail"
          onChange={(nextIndex) => {
            const nextStep = steps[nextIndex];
            if (!nextStep?.enabled) return;
            onNavigate?.(nextStep.key);
          }}
          items={steps.map((step) => ({
            key: step.key,
            title: buildStepTitle(step),
            content: <span className="workflow-rail-description">{step.description}</span>,
            disabled: !step.enabled,
          }))}
        />
      </div>
    </div>
  );
}
