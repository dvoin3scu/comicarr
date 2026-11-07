/**
 * MSW server setup for Node.js test environment.
 */

import { setupServer } from "msw/node";
import { handlers } from "./handlers";
import { forkHandlers } from "./forkHandlers";

// Create the MSW server with our handlers
export const server = setupServer(...forkHandlers, ...handlers);
