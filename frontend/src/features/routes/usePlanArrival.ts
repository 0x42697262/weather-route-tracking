import { useEffect, useRef } from "react";
import { useTripPlan } from "@/api/queries";
import { useUiActions } from "@/state/context";

export function usePlanArrival(): void {
  const plan = useTripPlan();
  const { showPlan } = useUiActions();
  const tripRef = useRef(plan.data);
  const arrivedAt = plan.dataUpdatedAt;
  useEffect(() => {
    tripRef.current = plan.data;
  }, [plan.data]);
  useEffect(() => {
    const trip = tripRef.current;
    if (trip === undefined) {
      return;
    }
    showPlan(trip.recommended_route_id ?? trip.routes[0]?.id ?? null);
  }, [arrivedAt, showPlan]);
}
