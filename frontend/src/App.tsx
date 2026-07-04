import { createHashRouter, RouterProvider } from "react-router-dom";

import BuildMapView from "./views/BuildMapView";
import PlanView from "./views/PlanView";
import ProjectsView from "./views/ProjectsView";

const router = createHashRouter([
  { path: "/", element: <ProjectsView /> },
  { path: "/projects/:projectId/plan", element: <PlanView /> },
  { path: "/build/:buildMapId", element: <BuildMapView /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
