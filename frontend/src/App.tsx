import { createHashRouter, RouterProvider } from "react-router-dom";

import PlanView from "./views/PlanView";
import ProjectsView from "./views/ProjectsView";

const router = createHashRouter([
  { path: "/", element: <ProjectsView /> },
  { path: "/projects/:projectId/plan", element: <PlanView /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
