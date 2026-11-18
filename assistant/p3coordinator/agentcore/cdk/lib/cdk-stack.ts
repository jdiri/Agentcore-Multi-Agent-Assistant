import { AgentCoreApplication, type AgentCoreApplicationProps } from '@aws/agentcore-cdk';
import { Stack, type StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

/** Support's Bedrock Knowledge Base (an ID, not an ARN). */
const SUPPORT_KB_ID = 'NEQY0WPAHT';
/** The model Support answers with; must match what was tested locally. */
const SUPPORT_MODEL_ID = 'deepseek.v3.2';

export interface AgentCoreStackProps extends StackProps {
  /** Props for the AgentCore application, produced by transformAgentCoreJson from agentcore/agentcore.json. */
  application: AgentCoreApplicationProps;
}

/**
 * The stack the AgentCore CLI deploys. Everything declared in agentcore/agentcore.json is
 * created by the AgentCoreApplication construct. Add your own resources below it and wire
 * them to your runtimes and harnesses through the application's accessors.
 */
export class AgentCoreStack extends Stack {
  public readonly application: AgentCoreApplication;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);
    this.application = new AgentCoreApplication(this, 'Application', props.application);

    // Example: give a runtime a DynamoDB table.
    //
    // import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
    // const orders = new dynamodb.Table(this, 'Orders', {
    //   partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
    // });
    // const checkout = this.application.runtime('checkout'); // or .harness('support')
    // checkout.grantReadWrite(orders);
    // checkout.addEnvironmentVariable('ORDERS_TABLE', orders.tableName);

    // Support (Track B) runs inside the coordinator runtime and searches the Bedrock Knowledge
    // Base directly (D6). The KB was created in the console, so it is referenced by ID; the ARN is
    // built from this stack's account and region at deploy time, so no account ID is in the repo.
    // Setting P3_KB_ID is what switches the runtime from the stub Support to the real one.
    // Model invoke needs no grant here: the runtime role already allows Bedrock foundation models.
    const coordinator = this.application.runtime('coordinator');
    coordinator.addEnvironmentVariable('P3_KB_ID', SUPPORT_KB_ID);
    coordinator.addEnvironmentVariable('P3_SUPPORT_MODEL_ID', SUPPORT_MODEL_ID);
    coordinator.grant(
      ['bedrock:Retrieve'],
      [`arn:${this.partition}:bedrock:${this.region}:${this.account}:knowledge-base/${SUPPORT_KB_ID}`],
    );
  }
}
